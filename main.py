<<<<<<< HEAD
import os
import spacy
from spacy.tokens import Doc
from spacy.matcher import Matcher
from spacy.lang.en import English
import json
from datetime import datetime
from dateutil.parser import parse


def main():

	# create a prediction object
	test = trainPredict()


	test.newQuery("i want to take a train to manchester airport from london liverpool street at 2:30 PM on sunday")

	while True:
		test.newQuery()

class trainPredict():

	def __init__(self):

		# key tiploc : {name longname alpha3}
		self.days = {}

		self.stationPatterns = []

		self.nlp = spacy.load("en_core_web_sm")

		self.stationRuler = self.nlp.add_pipe("entity_ruler", before='ner')

		# read the csv file
		self.loadFromCsv()

		#self.stationRuler.add_patterns([{"label": "domLovesCock", "pattern": "manchester"}])
		self.stationRuler.add_patterns(self.stationPatterns)
		#self.stationRuler.add_patterns([{"label": "domLovesFatBigBulgingVeinyCocks", "pattern": [{"LOWER": "manchester"}, {"LOWER": "airport"}]}])

		
		
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

		if query == None:
			query = input("Hello! How can I help?\n> ")


		current_datetime = datetime.now()
		date = current_datetime.date() # will need too check with user if this is right
		time = current_datetime.time()
		toStation = None # location defult like time
		fromStation = None
		
		# put query through nlp pipeline
		doc = self.nlp(query)
		for i, token in enumerate(doc):

			
			if token.text == "to":
				if doc[i+1].ent_type_:
					toStation = doc[i + 1].ent_id_
			elif token.text == "from":
				if doc[i+1].ent_type_:
					fromStation = doc[i + 1].ent_id_
			elif token.text == "on": # date
				if doc[i+1].ent_type_:
					date = parse(doc[i + 1].text)
			elif token.text == "at": # time
				if doc[i+1].ent_type_:
					time = doc[i + 1].ent_id_

		while toStation == None:

			if fromStation != None:
				query = input(f"I see you want to travel from {fromStation}, where are you going to\n> ")

			else:
				query = input(f"Where are you travelling to?\n> ")

			doc = self.nlp(query)

			for token in doc:
				if token.ent_type_:
					toStation = token.ent_id_


		print(f'toStation: {toStation}, fromStation: {fromStation}, date: {date}, time:, {time}')





	


if __name__ == '__main__':
	main()
=======
import os
import spacy
from spacy.tokens import Doc
from spacy.matcher import Matcher
from spacy.lang.en import English
import json
from dateutil import parser
from datetime import datetime


def main():

	# create a prediction object
	test = trainPredict()


	#test.newQuery("i want to take a train to manchester airport from london liverpool street")

	while True:
		test.newQuery()

class trainPredict():

	def __init__(self):

		# key tiploc : {name longname alpha3}
		#self.stations = {}

		self.stationPatterns = []

		self.nlp = spacy.load("en_core_web_sm")

		self.stationRuler = self.nlp.add_pipe("entity_ruler", before='ner')

		# read the csv file
		self.loadFromCsv()

		#self.stationRuler.add_patterns([{"label": "domLovesCock", "pattern": "manchester"}])
		self.stationRuler.add_patterns(self.stationPatterns)
		#self.stationRuler.add_patterns([{"label": "domLovesFatBigBulgingVeinyCocks", "pattern": [{"LOWER": "manchester"}, {"LOWER": "airport"}]}])

		
		
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
	def newQuery(self):


		query = input("Hello! How can I help?\n> ")


		current_datetime = datetime.now()
		date = current_datetime.date() # will need too check with user if this is right
		time = current_datetime.time()
		toStation = None # location defult like time
		fromStation = None
		
		# put query through nlp pipeline
		doc = self.nlp(query)
		for i, token in enumerate(doc):

			
			if token.text == "to":
				if doc[i+1].ent_type_:
					toStation = doc[i + 1].ent_id_
			elif token.text == "from":
				if doc[i+1].ent_type_:
					fromStation = doc[i + 1].ent_id_
			elif token.text == "on": # date
				if doc[i+1].ent_type_:
					fromStation = doc[i + 1].ent_id_
			elif token.text == "at": # time
				if doc[i+1].ent_type_:
					fromStation = doc[i + 1].ent_id_

		while toStation == None:

			if fromStation != None:
				query = input(f"I see you want to travel from {fromStation}, where are you going to\n> ")

			else:
				query = input(f"Where are you travelling to?\n> ")

			doc = self.nlp(query)

			for token in doc:
				if token.ent_type_:
					toStation = token.ent_id_


		print(f'toStation: {toStation}, fromStation: {fromStation}')





	


if __name__ == '__main__':
	main()
>>>>>>> d74509c91ffaa08040147b7d786b76de1091c055
