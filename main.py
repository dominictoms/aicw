import os
import io
import json
import re
import logging
import math
import sys

import spacy
from spacy.tokens import Doc
from spacy.matcher import Matcher
from spacy.lang.en import English

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

from datetime import time, datetime, timedelta

from dateutil.parser import parse

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from threading import Thread

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

history = []

# web server stuff as globals
@app.route('/')
def index():
	return render_template('index.html')

@socketio.on('connect')
def handle_connection():
	for message in history:
		socketio.emit('message', message)

@socketio.on('message')
def handle_message(message):
	trainPredict.webInput(message)
	trainPredict.newQuery(message)

def main():

	# run the query
	trainPredict.newQuery()

class trainPredict():

	def __init__(self):

		# key tiploc : {name longname alpha3}
		self.days = {}

		self.stationPatterns = []

		self.nlp = spacy.load("en_core_web_sm")

		self.stationRuler = self.nlp.add_pipe("entity_ruler", before='ner')

		wordTimePatterns = [
			{"label": "WORDTIME", "pattern": [{"LOWER": "midday"}], 'id': 0},
			{"label": "WORDTIME", "pattern": [{"LOWER": "midnight"}], 'id': 1},
			{"label": "WORDTIME", "pattern": [{"LOWER": "quarter"},{"LOWER": "to"}], 'id': 2},
			{"label": "WORDTIME", "pattern": [{"LOWER": "quarter"},{"LOWER": "past"}], 'id': 3},	
			{"label": "WORDTIME", "pattern": [{"LOWER": "half"},{"LOWER": "past"}], 'id': 4},
			]

		# read the csv file
		self.loadFromCsv()

		#self.stationRuler.add_patterns([{"label": "domLovesCock", "pattern": "manchester"}])
		self.stationRuler.add_patterns(self.stationPatterns)
		self.stationRuler.add_patterns(wordTimePatterns)
		#self.stationRuler.add_patterns([{"label": "domLovesFatBigBulgingVeinyCocks", "pattern": [{"LOWER": "manchester"}, {"LOWER": "airport"}]}])

		# get defaults
		current_datetime = datetime.now()
		self.date = current_datetime.date() # will need too check with user if this is right
		self.time = current_datetime.time()
		self.toStation = None # location defult like time
		self.fromStation = None


	def sendMessage(self, message):
		print(f"TrainRunner: {message} ")
		socketio.emit('message', f"TrainRunner: {message}")
		history.append("TrainRunner: " + message)

	def userInput(self):
		message = input()
		socketio.emit('message', f"User: {message}")
		history.append("User: " + message)
		return message

	def webInput(self, message):
		print(f"User: {message} ")
		socketio.emit('message', f"User: {message}")
		history.append("User: " + message)

	def loadFromCsv(self):

		# open the csv file containing every station
		script_dir = os.path.dirname(os.path.abspath(__file__))
		with open(os.path.join(script_dir, "stations.csv"), 'r') as file:

			# get all the lines in the csv file
			lines = file.readlines()

			# remove header from csv file
			lines.pop(0)

			# iterate through every line
			for line in lines:

				# strip whitespace and linebreaks from line
				line = line.replace('"', '').replace('\n', '')

				# split line at commas
				namesSplit = line.split(',')

				# add station to dict, use the tiploc as the key
				name = namesSplit[0]
				longname = namesSplit[1]
				alpha3 =  namesSplit[4]
				tiploc =namesSplit[3]

				# add longname
				longname_patterns = []
				for word in longname.split():
					longname_patterns.append({"LOWER": word.lower()})

				self.stationPatterns.append(
					{"label": "STATION", "pattern": longname_patterns, 'id': tiploc}
				)

				if len(longname_patterns) >= 3:

					longname_patterns = longname_patterns[:-2]

					if longname_patterns[0] == 'London':
						longname_patterns.pop(0)

					self.stationPatterns.append(
						{"label": "STATION", "pattern": longname_patterns, 'id': tiploc}
					)


				# add name
				name_patterns = []
				for word in name.split():
					name_patterns.append({"LOWER": word.lower()})

				self.stationPatterns.append(
					{"label": "STATION", "pattern": name_patterns, 'id': tiploc}
				)

				while "LONDON" in name_patterns:
					name_patterns.remove("LONDON")

				self.stationPatterns.append(
					{"label": "STATION", "pattern": name_patterns, 'id': tiploc}
				)


	# run a new query
	def newQuery(self, query  = None):

		webRequest = False

		message = "Hello! How can I help?"


		if self.toStation != None:
			message = f"I see you want to travel to {self.toStation}, which station would you like to go from?"

		if self.fromStation != None:
			message = f"I see you want to travel from {self.fromStation}, where is your final destination?"

		if self.fromStation != None and self.toStation != None:
			message = f"I see you want to travel to {self.toStation} from {self.fromStation}, finding your ticket now!"

		self.sendMessage(message)

		if query == None:
			query = self.userInput()

		else:
			webRequest = True

		#if self.toStation != None and self.fromStation != None:
		#	message = f"I see you want to travel to {self.toStation} from {self.fromStation}, finding your ticket now!"




		
		# put query through nlp pipeline
		doc = self.nlp(query)
		for i, token in enumerate(doc):

			
			if token.text == "to":
				if doc[i+1].ent_type_:
					self.toStation = doc[i + 1].ent_id_
			elif token.text == "from":
				if doc[i+1].ent_type_:
					self.fromStation = doc[i + 1].ent_id_
			elif token.text == "on":
				if doc[i+1].ent_type_:
					self.date = parse(doc[i + 1].text)
			elif token.text == "at":
				if doc[i+1].ent_type_ == "WORDTIME":

					self.time = doc[i + 1].ent_id_
				else:
					self.time = self.toTime(doc[i + 1].text + ' ' +	doc[i + 2].text)

		'''
		# get a to station
		while self.toStation == None:

			if self.fromStation != None:
				self.sendMessage(f"I see you want to travel from {self.fromStation}, where are you going to")
				query = self.userInput()

			else:
				self.sendMessage("Where are you travelling to?")
				query = self.userInput()

			doc = self.nlp(query)

			for token in doc:
				if token.ent_type_:
					self.toStation = token.ent_id_

		# get a from station
		while self.fromStation == None:

			if self.toStation != None:
				self.sendMessage(f"I see you want to travel to {self.toStation}, where are you travelling from?")
				query = self.userInput()

			else:
				self.sendMessage("Where are you travelling from?")
				query = self.userInput()

			doc = self.nlp(query)

			for token in doc:
				if token.ent_type_:
					self.fromStation = token.ent_id_
		'''

		if self.toStation != None and self.fromStation != None:


			# format the date for the web scraping
			formatted_date = self.date.strftime("%d %m %y")
			day, month, year = formatted_date.split()

			# format the time for the web scraping
			formatted_time = self.time.strftime("%H %M")
			hour, minute = formatted_time.split()

			# round minute up to the next 15 minutes
			minute = str(math.ceil(int(minute) / 15) * 15)

			if int(minute) >= 60:
				minute = '00'
				hour = str(int(hour) + 1)

				if len(hour) == 1:
					hour = '0' + hour


			url = self.getUrl(self.fromStation, self.toStation, day, month, year, hour, minute)


			price = self.getPrice(url)
			
			if price != None:
				self.sendMessage(f"The cheapest ticket is {price}!")
				self.sendMessage(f"You can get a ticket here: {url}")

			else:
				self.sendMessage(f"You can get a ticket here: {url}")

		elif webRequest == False:
			self.newQuery()




	def toTime(self, timeStr):


		match = re.search(r'(\d{1,2}):(\d{2})(?:\s?(AM|PM))?', timeStr, re.IGNORECASE)
		if match:
			hour, minute, period = match.groups()
			hour = int(hour)
			minute = int(minute)
			if period and period.lower() == 'pm' and hour != 12:
				hour += 12
			elif period and period.lower() == 'am' and hour == 12:
				hour = 0
			foundTime = time(hour, minute)
		return(foundTime)



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

			# return the price
			return re.search(r"£\d+(\.\d+)?", price_box.get_attribute("aria-label")).group()

		# something fucked up
		except:
			return None

	# get the url from national rail
	def getUrl(self, origin, destination, date, month, year, hour, minute):
		return f'https://www.nationalrail.co.uk/journey-planner/?type=single&origin={origin}&destination={destination}&leavingType=departing&leavingDate={date}{month}{year}&leavingHour={hour}&leavingMin={minute}&adults=1&extraTime=0#O'
		
# create a prediction object
trainPredict = trainPredict()

if __name__ == "__main__":

	# run the chatbot in the terminal
	terminal_thread = Thread(target=main)
	terminal_thread.start()

	# run the chatbot in the browser
	socketio.run(app, port=5001)
