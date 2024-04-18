import spacy
from spacy.tokens import Doc
from spacy.matcher import Matcher
from spacy.tokens import Span
from spacy.language import Language

nlp = spacy.load("en_core_web_sm")
matcher = Matcher(nlp.vocab)

# TODO put this in the class
stationTokens = [] 

# spacy function to check for station name in query
@Language.component("station_detector")
def detect_stations(doc):

	# TODO don't use global
	global stationTokens

	# update docs has station paraameter if station is in doc
	doc._.has_station  = any(token.text.lower() in stationTokens for token in doc) 

	# send the doc back
	return doc 

def main():

	# create a prediction object
	test = trainPredict()

	# test on a station we know exists
	test.newQuery("London Liverpool Street Rail Station")

	# prompt user to enter station names forever
	while True:
		test.newQuery(input('enter station: '))
		

class trainPredict():


	def __init__(self):

		# key tiploc : {name longname alpha3}
		self.stations = {}

		# read the csv file
		self.loadFromCsv()

		# TODO don't use global
		global stationTokens

		# Add custom attribute to Doc using extension attribute
		Doc.set_extension('has_station', default=False)

		# Add the custom component to the spaCy pipeline using the string name
		nlp.add_pipe("station_detector", last=True)
		
		
	def loadFromCsv(self):

		# TODO don't use global
		global stationTokens

		# open the csv file containing every station
		with open("./stations.csv", 'r') as file:

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
				self.stations[namesSplit[3]] = {
					'name': namesSplit[0],
					'longname': namesSplit[1],
					'alpha3': namesSplit[4]
				}

				# TODO use dicts and not a massive list
				stationTokens.append(namesSplit[1])

	# run a new query
	def newQuery(self, query):

		# put query through nlp pipeline
		doc = nlp(query)

		if doc._.has_station:
			print("station found")
		else:
			print("no station found")


if __name__ == '__main__':
	main()
