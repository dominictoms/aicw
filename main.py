import os
import io
import json
import re
import logging
import math
import sys

import spacy
from spacy.tokens import Doc, Token
from spacy.matcher import Matcher
from spacy.pipeline import EntityRuler
from spacy.language import Language
import json
from datetime import datetime, time
from dateutil.parser import parse
import re
from word2number import w2n

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
	testData = [
	"i want to take a return train to manchester airport from diss at 10:15 PM on sunday with one adult and 1 child",
	"i want to get a train at manchester airport and arrive at diss at 10:00 on sunday",
	"i want to go from diss to norwich",
	"i want to go from norwich to diss",
	"i want to leave diss at 12:30 and go to norwich",
	"i want to depart norwich at 7:45 and go to diss",
	"i want to arrive at norwich from diss",
	"7:30 i want to leave norwich for diss",
	"diss to norwich",
	"norwich from diss",
	"i want to be at diss at 7:30am, from norwich",
	"i must reach diss prompty, get me there from norwich",
	"my destination is diss, i am currently at norwich",
	"get me to my sneaky link, i'm in norwich and shes in diss",
	"they'll break my legs if i don't leave norwich tonight, get me to diss",
	"get me to diss! i'm in norwich right now",
	"get me away from norwich, i want to be in diss"
	]

	print('here')

	
	#trainPredict.new_query("i want to take a train to manchester airport from diss at 10:15 PM on sunday")
	#trainPredict.new_query("i want to get a train at manchester airport and arrive at london liverpool street at 10:00 on sunday")
	for test in testData:
		trainPredict.new_query(test)

		print('\n----------------------------------------------------------\n')
	

@Language.component("info_semantic")
def info_semantic(doc):
    """Custom spaCy pipeline component to label tokens based on semantic similarity."""
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
	_instance = None

	@staticmethod
	def get_instance():

		if TrainPredict._instance is None:
			TrainPredict()
		return TrainPredict._instance

	def __init__(self):


		if TrainPredict._instance is not None:
			raise Exception("This class is a singleton!")
		else:
			TrainPredict._instance = self
        
        # Load the spaCy NLP model
		self.nlp = spacy.load("en_core_web_md")
        
        # Initialize custom extensions
		Token.set_extension('info', default=None, force=True)
		Token.set_extension('identical', default=None, force=True)
        
        # Initialize the EntityRuler for station names and word times
		self.stationRuler = self.nlp.add_pipe("entity_ruler", before='ner')
		self.load_stations()
        
        # Add custom component for semantic analysis by registered name
		self.nlp.add_pipe("info_semantic", after="entity_ruler")
        
        # Key semantic words and their roles
		self.info_words = {
            "to": [["to", 1, "STATION"]],
            "from": [["from", 1, "STATION"]],
            "by": [["by", 1, "TIME"]],
            "on": [["on", 1, "DATE"]],
			
			"adult": [["adult",-1,"NUM"]],
			"child": [["child",-1,"NUM"]],
			"people": [["adult",-1,"NUM"]],
			"ticket": [["adult",0,"None"]],
			
			
			"back": [["back",0, "None"]],
            #complex
			"tickets": [["tickets",-1,"NUM"]],
            "at": [["from", 1, "STATION"], ["by", 1, "TIME"]],
			"leave" : [[["at","by"],2,"TIME"],["from",2,"STATION"],["from",2,"STATION"]],
            "arrive": [[["at","to"], 2, "STATION"], ["by", 2, "TIME"]],
            "depart": [["at", 2, "STATION"],["from", 2, "STATION"], ["by", 2, "TIME"],["on", 2, "DATE"],["from",1,"STATION"]],
			"in": [["to	",1,"STATION"]],
			"is": [["to",1,"STATION"]],
			"return": [["adult", -1, "NUM","RETURN"],["from",2,"STATION","RETURN"],["to",2,"STATION","RETURN"],["by",2,"TIME","RETURN"],["on", 2, "DATE","RETURN"],["isReturn", 0,"BACK","RETURN"]],
			"returns":  [["adult", -1, "NUM","RETURN"],["from",2,"STATION","RETURN"],["to",2,"STATION","RETURN"],["by",2,"TIME","RETURN"],["on", 2, "DATE","RETURN"],["isReturn", 0,"BACK","RETURN"]],
			
			#v complex

			
        }
        
		print('here?')

        # Preparing a matcher for semantic similarity
		self.prepare_info_tokens()

        # Similarity threshold
		self.sim_thresh = 0.6

	def prepare_info_tokens(self):


		self.info_tokens = {word: self.nlp(word)[0] for word in self.info_words if self.nlp(word)[0].has_vector}
		#print(f"Info tokens prepared: {self.info_tokens}")

	def load_stations(self):
        
		script_dir = os.path.dirname(os.path.abspath(__file__))
		with open(os.path.join(script_dir, "stations.csv"), 'r') as file:
			lines = file.readlines()
			lines.pop(0)  # Remove the header
			for line in lines:
				line = line.strip().replace('"', '')
				if line:
					parts = line.split(',')
					name, longname, tiploc = parts[0], parts[1], parts[3]
                    # Add patterns for the full name and short name
					self.stationRuler.add_patterns([
                        {"label": "STATION", "pattern": [{"LOWER": word.lower()} for word in longname.split()], "id": tiploc},
                        {"label": "STATION", "pattern": [{"LOWER": word.lower()} for word in name.split()], "id": tiploc}
                    ])
	

	def new_query(self, query=None):
		complete = False
		while not complete:
			while query is None:
				query = input("Hello! How can I help?\n> ")
			complete = self.output(query)

	def processQuery(self, query):
		doc = self.nlp(query)
		certain = [None,None,None,None,None,None,None]
		to_station, from_station, journey_date, journey_time, adultTickets, childTickets = None, None, None, None, None, None
		skip = False
		for token in doc:
			if not skip:
				if token._.info:
					#print(token._.info)
					for meaning in token._.info:
						#print(token)

						#print(meaning)

						if meaning[1] >= 1:
							data_pos = token.i + 1
						elif meaning[1] == -1:
							data_pos = token.i - 1
						if meaning[1] == 2 and data_pos < len(doc):
								meaning[1] -= 1
								if isinstance(meaning[0], list):

									if doc[data_pos].text == meaning[0][0]:
										#print(doc[data_pos].text)
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
						#print('vfgggfuhvfthuftufvtucftfrdtrd', meaning[0])
						#print(doc[data_pos])
						#print(f"station {doc[data_pos]} datapos {data_pos} < len {len(doc)}    ent: {doc[data_pos].ent_type_}  meaning {meaning}")
						isNum = "NUM" if doc[data_pos].like_num else "NOTNUM"
						#print(meaning)
						#print(f"len{len(meaning)}")
						if data_pos < len(doc) and (doc[data_pos].ent_type_ == meaning[2] or isNum == meaning[2] or 0== meaning[1]): # broke
							print(meaning)
							print(f"len{len(meaning)}")
							if len(meaning) == 4:
								certain[6] = True
							#print(3456789098765434567)
							#print(meaning)
							if meaning[0] == "from":
								#print(3456789)
								if token._.identical:
									certain[0] = True
								else:
									certain[0] = False
									#print(certain[0])
								from_station = doc[data_pos].ent_id_ 
								break
							elif meaning[0] == "to":
								#print(token._.identical)
								if token._.identical:
									certain[1] = True
								else:
									certain[1] = False
								to_station = doc[data_pos].ent_id_
								break
							elif meaning[0] == "on":
								#print(journey_date)
								if token._.identical:
									certain[2] = True
								else:
									certain[2] = False
									#print(certain[2])
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
								if  token._.identical:
									certain[5] = True
								else:
									certain[5] = False
									
								childTickets = w2n.word_to_num(doc[data_pos].text)
								print(certain[5])
								break
							

			else:
				skip = False
		current_datetime = datetime.now()
		if journey_date == None:
			journey_time = current_datetime.time()
			certain[3] == False

		if journey_date == None:
			journey_date = current_datetime.date() 
			certain[3] == False
		print(certain)
		return(certain, to_station, from_station, journey_date, journey_time, adultTickets, childTickets)
		#print(query)
		#print(f'To: {to_station}, From: {from_station}, Date: {journey_date}, Time: {journey_time}')
		
	def output(self, query):
		
		
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
				print(f'To: {to_station}, From: {from_station}, Date: {journey_date}, Time: {journey_time}, child {childTickets}, adult {adultTickets}, return {certain[6]}')
				query = input(output)

		
		print(query)
		print(f'To: {to_station}, From: {from_station}, Date: {journey_date}, Time: {journey_time}, child {childTickets}, adult {adultTickets}, return {certain[6]}')
		return(True)

				

	def to_time(self, time_str):


		match = re.search(r'(\d{1,2}):(\d{2})(?:\s?(AM|PM))?', time_str, re.IGNORECASE)
		if match:
			hour, minute, period = match.groups()
			hour, minute = int(hour), int(minute)
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
trainPredict = TrainPredict()

if __name__ == "__main__":

	print('here!')

	# run the chatbot in the terminal
	terminal_thread = Thread(target=main)
	terminal_thread.start()

	# run the chatbot in the browser
	socketio.run(app, port=5001)
