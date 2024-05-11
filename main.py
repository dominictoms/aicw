import os
import io
import json
import re
import logging
import math
import sys
import json
import re
from datetime import time, datetime, timedelta
from dateutil.parser import parse
from threading import Thread

# spacy for natural language processing
import spacy
from spacy.tokens import Doc, Token
from spacy.matcher import Matcher
from spacy.pipeline import EntityRuler
from spacy.language import Language
from datetime import datetime, time
from dateutil.parser import parse
from word2number import w2n

# selenium for web scraping
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# flask and flask_socketio for web server
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

# hacky fix to remove flask opening message
cli = sys.modules["flask.cli"]
cli.show_server_banner = lambda *x: None

# make flask and socketio
app = Flask(__name__)
app.logger.disabled = True
socketio = SocketIO(app, logger=False)

# don't spam console with this stuff
logging.getLogger("socketio").setLevel(logging.ERROR)
logging.getLogger("engineio").setLevel(logging.ERROR)
logging.getLogger("werkzeug").setLevel(logging.ERROR)

# global list of conversation history, for web server
history = []

# TODO feels wrong to have this global
trainPredict = None

# route the root of the web server to index.html
@app.route("/")
def index():
	return render_template("index.html")

# populate ui with chat history on connection
@socketio.on("connect")
def handleConnection():
	for message in history:
		socketio.emit("message", message)

# when the user sends a message from the gui 
@socketio.on("message")
def handleMessage(message):
	trainPredict.webInput(message)
	trainPredict.newQuery(message)

def main():
	# start a new query
	trainPredict.newQuery()

@Language.component("info_semantic")
def infoSemantic(doc):

	# TODO pike comment this i have no idea what this does
	trainPredictObject = TrainPredict.getInstance()
	for token in doc:
		if token.text.lower() in trainPredictObject.infoWords:
			token._.identical = True
			token._.info = trainPredictObject.infoWords[token.text.lower()]
		else:
			for word, infoToken in trainPredictObject.infoTokens.items():
				if token.has_vector and token.similarity(infoToken) > trainPredictObject.simThresh:
					token._.identical = False
					token._.info = trainPredictObject.infoWords[word]
					break
	return doc

class TrainPredict:

	# trainpredict is a singleton i guess
	_instance = None

	# this does some singleton related stuff idk
	@staticmethod
	def getInstance():
		if TrainPredict._instance is None:
			TrainPredict()
		return TrainPredict._instance

	def __init__(self):

		# singleton stuff
		if TrainPredict._instance is not None:
			raise Exception("trainpredict is a singleton!")
		else:
			TrainPredict._instance = self

		# let her send the opening line ;)
		self.chatbotSpeech("Welcome to Trainrunner! How may I help xx")
		
		# set up spacy
		self.nlp = spacy.load("en_core_web_md")
		
		# custom tokens for info items and identical items
		Token.set_extension("info", default=None, force=True)
		Token.set_extension("identical", default=None, force=True)
   
		# add the station ruler to spacy before named entity recognition 
		self.stationRuler = self.nlp.add_pipe("entity_ruler", before="ner")
		self.loadStations()
		
		# add custom component for semantic analysis by registered name
		self.nlp.add_pipe("info_semantic", after="entity_ruler")
		
		# key semantic words and their roles
		self.infoWords = {

			# the very simple words, like to and from
			"to": [["to", 1, "STATION"]],
			"from": [["from", 1, "STATION"]],
			"by": [["by", 1, "TIME"]],
			"on": [["on", 1, "DATE"]],
			
			# words to handle more specific requests like different tickets
			"adult": [["adult",-1,"NUM"]],
			"child": [["child",-1,"NUM"]],
			"people": [["adult",-1,"NUM"]],
			"ticket": [["adult",0,"None"]],
			"back": [["back",0, "None"]],
			
			# very complex queries 
			"tickets": [
				["tickets",-1,"NUM"]
			],
			"at": [
				["from", 1, "STATION"],
				["by", 1, "TIME"]
			],
			"leave" : [
				[["at","by"],2,"TIME"],
				["from",2,"STATION"],
				["from",2,"STATION"]
			],
			"arrive": [
				[["at","to"], 2, "STATION"],
				["by", 2, "TIME"]
			],
			"depart": [
				["at", 2, "STATION"],
				["from", 2, "STATION"],
				["by", 2, "TIME"],
				["on", 2, "DATE"],
				["from",1,"STATION"]
			],
			"in": [
				["to	",1,"STATION"]
			],
			"is": [
				["to",1,"STATION"]
			],
			"return": [
				["adult", -1, "NUM","RETURN"],
				["from",2,"STATION","RETURN"],
				["to",2,"STATION","RETURN"],
				["by",2,"TIME","RETURN"],
				["on", 2, "DATE","RETURN"],
				["isReturn", 0,"BACK","RETURN"]
			],
			"returns":	[
				["adult", -1, "NUM","RETURN"],
				["from",2,"STATION","RETURN"],
				["to",2,"STATION","RETURN"],
				["by",2,"TIME","RETURN"],
				["on", 2, "DATE","RETURN"],
				["isReturn", 0,"BACK","RETURN"]
			]
		}
		
		# preparing a matcher for semantic similarity
		self.prepareInfoTokens()

		# similarity threshold
		self.simThresh = 0.6

	# function for setting info_tokens variable
	def prepareInfoTokens(self):
		self.infoTokens = {
			word: self.nlp(word)[0] for word in self.infoWords if self.nlp(word)[0].has_vector
		}

	# load all the stations from the csv file
	def loadStations(self):
		
		# read the csv file
		scriptDir = os.path.dirname(os.path.abspath(__file__))
		with open(os.path.join(scriptDir, "stations.csv"), "r") as file:

			# put all the lines in a list
			lines = file.readlines()

			# since the first line is a header, remove it
			lines.pop(0) 

			# iterate through every line
			for line in lines:

				# clean the line up
				line = line.strip().replace("\"", "")

				# if the line is empty, give it a miss
				if not line:
					continue

				# extract all the info from the csv
				parts = line.split(",")
				name, longname, tiploc = parts[0], parts[1], parts[3]

				# add the station longname and name to the station ruler, tiploc as id
				self.stationRuler.add_patterns([
					{
						"label": "STATION",
						"pattern": [
							{"LOWER": word.lower()} for word in longname.split()
						],
						"id": tiploc
					},
					{
						"label": "STATION",
						"pattern": [
							{"LOWER": word.lower()} for word in name.split()
						],
						"id": tiploc
					}
				])

	# user messages chatbot from cli
	def cliInput(self):

		# get message from cli and add users name
		message = input()
		message = f"User: {message}"

		# output to gui (will stay in cli from input)
		socketio.emit("message", f"User: {message}")

		# add to history
		history.append("User: " + message)

		# send it back
		return message

	# user messages chatbot from web
	def webInput(self, message):

		# add the users name to the message
		message = f"User: {message}"

		# output to cli and gui
		print(message)
		socketio.emit("message", message)

		# add to history
		history.append(message)

	# chatbot messages user
	def chatbotSpeech(self, message):

		# add the chatbots name to the message
		message = f"TrainRunner: {message} "

		# output to cli and gui
		print(f"{message} ")
		socketio.emit("message", message)

		# add to history
		history.append(message)
	
	# function to start a new query
	def newQuery(self, query = None):

		# boolean to check if message was sent via cli or server
		webRequest = query != None
		
		# get input from cli if no query is provided
		if not webRequest:
			query = self.cliInput()

		# call the output function!
		self.output(query)

		# infinite loop the query prompt for the cli
		if not webRequest:
			self.newQuery()

	# actually process the query
	def processQuery(self, query):

		# nlp the doc
		doc = self.nlp(query)

		# list of which variables we're certain on
		certain = [None,None,None,None,None,None,None]
		toStation, fromStation, journeyDate, journeyTime, adultTickets, childTickets = None, None, None, None, None, None

		# this works wonders but i cannot comprehend what's happening here
		skip = False
		for token in doc:
			if not skip:
				if token._.info:
					for meaning in token._.info:
						if meaning[1] >= 1:
							dataPos = token.i + 1
						elif meaning[1] == -1:
							dataPos = token.i - 1
						if meaning[1] == 2 and dataPos < len(doc):
								meaning[1] -= 1
								if isinstance(meaning[0], list):
									if doc[dataPos].text == meaning[0][0]:
										meaning[0] = meaning[0][1]
										dataPos += 1
										skip = True
									else:
										continue
								else:
									if doc[dataPos].text == meaning[0]:
										dataPos += 1
										skip = True
									else:
										continue
						isNum = "NUM" if doc[dataPos].like_num else "NOTNUM"
						if dataPos < len(doc) and (doc[dataPos].ent_type_ == meaning[2] or isNum == meaning[2] or 0== meaning[1]): 
							if len(meaning) == 4:
								certain[6] = True
							if meaning[0] == "from":
								if token._.identical:
									certain[0] = True
								else:
									certain[0] = False
								fromStation = doc[dataPos].ent_id_ 
								break
							elif meaning[0] == "to":
								if token._.identical:
									certain[1] = True
								else:
									certain[1] = False
								toStation = doc[dataPos].ent_id_
								break
							elif meaning[0] == "on":
								if token._.identical:
									certain[2] = True
								else:
									certain[2] = False
								journeyDate = parse(doc[dataPos].text).date()
								break
							elif meaning[0] == "by":
								if token._.identical:
									certain[3] = True
								else:
									certain[3] = False
								journeyTime = self.toTime(doc[dataPos].text)
								break
							
							elif meaning[0] == "adult":
								if token.text == "adult" and token._.identical:
									certain[4] = True
								else:
									certain[4] = False
								adultTickets = w2n.word_to_num(doc[dataPos].text)
								break
							elif meaning[0] == "child":
								if	token._.identical:
									certain[5] = True
								else:
									certain[5] = False
								childTickets = w2n.word_to_num(doc[dataPos].text)
								break

			else:
				skip = False

		# we're currently assuming if no date is provided, do it right now
		currentDatetime = datetime.now()
		if journeyDate == None:
			journeyTime = currentDatetime.time()
			certain[3] == False

		if journeyDate == None:
			journeyDate = currentDatetime.date() 
			certain[3] == False

		# send it all back
		return certain, toStation, fromStation, journeyDate, journeyTime, adultTickets, childTickets

	# generate the response to the users query	
	def output(self, query):
		
		# we have a lot of variables
		certain, toStation, fromStation, journeyDate, journeyTime, adultTickets, childTickets = self.processQuery(query)
		# strings to store outputs
		uncertain = ""
		unknown = ""
		output = ""

		# meow
		for i, cat in enumerate(certain):

			# if we're uncertain
			if cat == False:
				if i == 0:
					uncertain += f"from {fromStation} "
				elif i == 1:
					uncertain += f"to {toStation} "
				elif i == 2:
					uncertain += f"on {journeyDate} "
				elif i == 3:
					uncertain += f"by {journeyTime} "
				elif i == 4:
					uncertain += f"for {adultTickets} adult(s) "
				elif i == 5:
					uncertain += f"for {childTickets} child(ren) "
				elif i == 6:
					returnStr = "youd like to return " if certain[6] else "you would not like to return"
					uncertain += f"and {returnStr}"

			# if we really have no idea
			elif cat == None:
				if i == 0:
					unknown += "from which station "
				elif i == 1:
					unknown += "to which station "
				elif i == 2:
					unknown += "what date "
				elif i == 3:
					unknown += "by what time "
				elif i == 4:
					unknown += "how many adult(s) "
				elif i == 5:
					unknown += "how many child(ren) "
				elif i == 6:
					unknown += "would you like to return "

		# double checck with the user
		if uncertain != "":
			output += ("just to check you want to go " + uncertain)

			# if theres also something we don't know
			if unknown != "":
				output += "and "

		# make the user speak english
		if unknown != "":
			output += ("would you mind providing more details, specifically: " + unknown)
			

		# if there's nothing more to check then we should have everything
		if output == "":

			# format the date for the web scraping
			formattedDate = journeyDate.strftime("%d %m %y")
			day, month, year = formattedDate.split()

			# format the time for the web scraping
			formattedTime = journeyTime.strftime("%H %M")
			hour, minute = formattedTime.split()

			# round minute up to the next 15 minutes
			minute = str(math.ceil(int(minute) / 15) * 15)

			# TODO this code sucks and will break i need to do this a better way
			if int(minute) >= 60:
				minute = "00"
				hour = str(int(hour) + 1)

				if len(hour) == 1:
					hour = "0" + hour

			# get the url for the journey from all of our data
			url = self.getUrl(fromStation, toStation, day, month, year, hour, minute)

			# use web scraping to grab the price from that url
			price = self.getPrice(url)
			
			# if we get a price, add it to the output
			if price != None:
				output += f"The cheapest ticket is {price}! "

			# add the url to the output
			output += f"You can get a ticket here: {url}"
		
		# we've figured out what to say, now say it
		self.chatbotSpeech(output)
				
	# converts a variety of time strings to python time object
	def toTime(self, timeStr):

		# god only knows what this regex is actually doing
		match = re.search(r"(\d{1,2}):(\d{2})(?:\s?(AM|PM))?", timeStr, re.IGNORECASE)

		# we got a time!
		if match:

			# convert the time to ints
			hour, minute, period = match.groups()
			hour, minute = int(hour), int(minute)

			# handle am and pm
			if period and period.lower() == "pm" and hour != 12:
				hour += 12
			elif period and period.lower() == "am" and hour == 12:
				hour = 0

			# send the time back!
			return time(hour, minute)

		# TODO actually handle this function failing
		return None


	# scrape the national rail website for ticket prices
	def getPrice(self, url):

		# configure chromium
		chromeOptions = Options()
		chromeOptions.add_argument("--headless")
		driver = webdriver.Chrome(options=chromeOptions)

		# load our url
		driver.get(url)

		# attempt to get price
		try:

			# id of box containing price
			priceId = "jp-class-jp-results-standard"

			# get the box containing the price
			priceBox = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, priceId)))

			# use regex to get the price from the div
			return re.search(r"£\d+(\.\d+)?", priceBox.get_attribute("aria-label")).group()

		# just return nothing if web scraping fails
		except:
			return None

	# get the url from national rail
	def getUrl(self, origin, destination, date, month, year, hour, minute):
		return f"https://www.nationalrail.co.uk/journey-planner/?type=single&origin={origin}&destination={destination}&leavingType=departing&leavingDate={date}{month}{year}&leavingHour={hour}&leavingMin={minute}&adults=1&extraTime=0#O"
		
# entry point
if __name__ == "__main__":

	# which port we wanna use
	guiPort = 5001

	# send link to gui
	print(f"Gui is running on http://127.0.0.1:{guiPort}")

	# start up trainPredict for the first time
	trainPredict = TrainPredict()

	# run the chatbot in the cli
	cliThread = Thread(target=main)
	cliThread.start()

	# run the chatbot in the browser in main thread
	socketio.run(app, port=guiPort)

