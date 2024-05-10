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
cli = sys.modules['flask.cli']
cli.show_server_banner = lambda *x: None

# make flask and socketio
app = Flask(__name__)
app.logger.disabled = True
socketio = SocketIO(app, logger=False)

# don't spam console with this stuff
logging.getLogger('socketio').setLevel(logging.ERROR)
logging.getLogger('engineio').setLevel(logging.ERROR)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# global list of conversation history, for web server
history = []

# route the root of the web server to index.html
@app.route('/')
def index():
	return render_template('index.html')

# populate ui with chat history on connection
@socketio.on('connect')
def handle_connection():
	for message in history:
		socketio.emit('message', message)

# when the user 
@socketio.on('message')
def handle_message(message):
	trainPredict.webInput(message)
	trainPredict.newQuery(message)

def main():

	# start a new query
	trainPredict.new_query()
	

@Language.component("info_semantic")
def info_semantic(doc):

	# TODO pike comment this i have no idea what this does
	train_predict = TrainPredict.get_instance()
	for token in doc:
		if token.text.lower() in train_predict.info_words:
			token._.identical = True
			token._.info = train_predict.info_words[token.text.lower()]
		else:
			for word, info_token in train_predict.info_tokens.items():
				if token.has_vector and token.similarity(info_token) > train_predict.sim_thresh:
					token._.identical = False
					token._.info = train_predict.info_words[word]
					break
	return doc

class TrainPredict:

	# trainpredict is a singleton i guess
	_instance = None

	# static method to get the current instance of trainpredict
	@staticmethod
	def get_instance():
		if TrainPredict._instance is None:
			TrainPredict()
		return TrainPredict._instance

	def __init__(self):

		# singleton stuff
		if TrainPredict._instance is not None:
			raise Exception("trainpredict is a singleton!")
		else:
			TrainPredict._instance = self
		
		# set up spacy
		self.nlp = spacy.load("en_core_web_md")
		
		# custom tokens for info items and identical items
		Token.set_extension('info', default=None, force=True)
		Token.set_extension('identical', default=None, force=True)
   
		# add the station ruler to spacy before named entity recognition 
		self.stationRuler = self.nlp.add_pipe("entity_ruler", before='ner')
		self.load_stations()
		
		# add custom component for semantic analysis by registered name
		self.nlp.add_pipe("info_semantic", after="entity_ruler")
		
		# key semantic words and their roles
		self.info_words = {

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
		self.prepare_info_tokens()

		# similarity threshold
		self.sim_thresh = 0.6

	# function for setting info_tokens variable
	def prepare_info_tokens(self):
		self.info_tokens = {
			word: self.nlp(word)[0] for word in self.info_words if self.nlp(word)[0].has_vector
		}

	# load all the stations from the csv file
	def load_stations(self):
		
		# read the csv file
		script_dir = os.path.dirname(os.path.abspath(__file__))
		with open(os.path.join(script_dir, "stations.csv"), 'r') as file:

			# put all the lines in a list
			lines = file.readlines()

			# since the first line is a header, remove it
			lines.pop(0) 

			# iterate through every line
			for line in lines:

				# clean the line up
				line = line.strip().replace('"', '')

				# if the line is empty, give it a miss
				if not line:
					continue

				# extract all the info from the csv
				parts = line.split(',')
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

	# user messages chatbox from cli
	def cliInput(self):
		message = input()
		socketio.emit('message', f"User: {message}")
		history.append("User: " + message)
		return message

	# user messages chatbox from web
	def webInput(self, message):
		print(f"User: {message} ")
		socketio.emit('message', f"User: {message}")
		history.append("User: " + message)

	# chatbox messages user
	def chatbotSpeech(self, message):
		print(f"TrainRunner: {message} ")
		socketio.emit('message', f"TrainRunner: {message}")
		history.append("TrainRunner: " + message)
	
	# function to start a new query
	def new_query(self, query=None):

		# boolean to check if message was sent via cli or server
		webRequest = query != None
		
		# chatbot says hi!
		self.chatbotSpeech("Hello! How can I help?")

		# get input from cli if no query is provided
		if not webRequest:
			query = self.cliInput()

		#TODO call the output function when ui is more stable
		#complete = self.output(query)

		# infinite loop the query prompt for the cli
		if not webRequest:
			self.new_query()

	# actually process the query
	def processQuery(self, query):

		# nlp the doc
		doc = self.nlp(query)

		# list of which variables we're certain on
		certain = [None,None,None,None,None,None,None]
		to_station, from_station, journey_date, journey_time, adultTickets, childTickets = None, None, None, None, None, None

		# this works wonders but i cannot comprehend what's happening here
		skip = False
		for token in doc:
			if not skip:
				if token._.info:
					for meaning in token._.info:
						if meaning[1] >= 1:
							data_pos = token.i + 1
						elif meaning[1] == -1:
							data_pos = token.i - 1
						if meaning[1] == 2 and data_pos < len(doc):
								meaning[1] -= 1
								if isinstance(meaning[0], list):
									if doc[data_pos].text == meaning[0][0]:
										meaning[0] = meaning[0][1]
										data_pos += 1
										skip = True
									else:
										continue
								else:
									if doc[data_pos].text == meaning[0]:
										data_pos += 1
										skip = True
									else:
										continue
						isNum = "NUM" if doc[data_pos].like_num else "NOTNUM"
						if data_pos < len(doc) and (doc[data_pos].ent_type_ == meaning[2] or isNum == meaning[2] or 0== meaning[1]): 
							print(meaning)
							print(f"len{len(meaning)}")
							if len(meaning) == 4:
								certain[6] = True
							if meaning[0] == "from":
								if token._.identical:
									certain[0] = True
								else:
									certain[0] = False
								from_station = doc[data_pos].ent_id_ 
								break
							elif meaning[0] == "to":
								if token._.identical:
									certain[1] = True
								else:
									certain[1] = False
								to_station = doc[data_pos].ent_id_
								break
							elif meaning[0] == "on":
								if token._.identical:
									certain[2] = True
								else:
									certain[2] = False
								journey_date = parse(doc[data_pos].text).date()
								break
							elif meaning[0] == "by":
								if token._.identical:
									certain[3] = True
								else:
									certain[3] = False
								journey_time = self.to_time(doc[data_pos].text)
								break
							
							elif meaning[0] == "adult":
								if token.text == "adult" and token._.identical:
									certain[4] = True
								else:
									certain[4] = False
								adultTickets = w2n.word_to_num(doc[data_pos].text)
								break
							elif meaning[0] == "child":
								if	token._.identical:
									certain[5] = True
								else:
									certain[5] = False
								childTickets = w2n.word_to_num(doc[data_pos].text)
								print(certain[5])
								break
							

			else:
				skip = False

		# we're currently assuming if no date is provided, do it right now
		current_datetime = datetime.now()
		if journey_date == None:
			journey_time = current_datetime.time()
			certain[3] == False

		if journey_date == None:
			journey_date = current_datetime.date() 
			certain[3] == False

		# send it all back
		return(certain, to_station, from_station, journey_date, journey_time, adultTickets, childTickets)

	# generate the response to the users query	
	def output(self, query):
		
		# go on forever and forever
		while True:
			certain, to_station, from_station, journey_date, journey_time, adultTickets,childTickets = self.processQuery(query)
			uncertain = ""
			unknown = ""
			output = ""
			for i, cat in enumerate(certain):
				#print(cat)
				if cat == False:
					if i == 0:
						uncertain += f"from {from_station} "
					elif i == 1:
						uncertain += f"to {to_station} "
					elif i == 2:
						uncertain += f"on {journey_date} "
					elif i == 3:
						uncertain += f"by {journey_time} "
					elif i == 4:
						uncertain += f"for {adultTickets} adult(s) "
					elif i == 5:
						uncertain += f"for {childTickets} child(ren) "
					elif i == 6:
						uncertain += f"and {'youd like to return 'if certain[6] else 'you would not like to return'}"
				elif cat == None:
					if i == 0:
						unknown += "from which station \n"
					elif i == 1:
						unknown += "to which station  \n"
					elif i == 2:
						unknown += "what date \n"
					elif i == 3:
						unknown += "by what time \n "
					elif i == 4:
						unknown += "how many adult(s) \n"
					elif i == 5:
						unknown += "how many child(ren) \n"
					elif i == 6:
						unknown += "would you like to return \n"
			print(certain)
			if uncertain != "":
				output += ("just to check you want to go " + uncertain)
				if unknown != "":
					output += "and "
			if unknown != "":
				output += ("would you mind providing more details, specifically: \n" + unknown)
				
			if output == "":
				break
				
			else:
				print(query)
				query = input(output)

		
		print(query)
		return True

				
	# converts a variety of time strings to python time object
	def to_time(self, time_str):

		# god only knows what this regex is actually doing
		match = re.search(r'(\d{1,2}):(\d{2})(?:\s?(AM|PM))?', time_str, re.IGNORECASE)

		# we got a time!
		if match:

			# convert the time to ints
			hour, minute, period = match.groups()
			hour, minute = int(hour), int(minute)

			# handle am and pm
			if period and period.lower() == 'pm' and hour != 12:
				hour += 12
			elif period and period.lower() == 'am' and hour == 12:
				hour = 0

			# send the time back!
			return time(hour, minute)

		# TODO actually handle this function failing
		return None


	# scrape the national rail website for ticket prices
	def getPrice(self, url):

		# configure chromium
		chrome_options = Options()
		chrome_options.add_argument("--headless")
		driver = webdriver.Chrome(options=chrome_options)

		# load our url
		driver.get(url)

		# attempt to get price
		try:

			# get the box containing the price
			price_box = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "jp-class-jp-results-standard")))

			# use regex to get the price from the div
			return re.search(r"£\d+(\.\d+)?", price_box.get_attribute("aria-label")).group()

		# just return nothing if web scraping fails
		except:
			return None

	# get the url from national rail
	def getUrl(self, origin, destination, date, month, year, hour, minute):
		return f'https://www.nationalrail.co.uk/journey-planner/?type=single&origin={origin}&destination={destination}&leavingType=departing&leavingDate={date}{month}{year}&leavingHour={hour}&leavingMin={minute}&adults=1&extraTime=0#O'
		
# TODO feels wrong to have this global
trainPredict = TrainPredict()

# entry point
if __name__ == "__main__":

	# run the chatbot in the terminal
	terminal_thread = Thread(target=main)
	terminal_thread.start()

	# run the chatbot in the browser in main thread
	socketio.run(app, port=5001)
