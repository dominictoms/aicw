import spacy
from spacy.tokens import Doc
from spacy.language import Language

# Define the list of specific words
specific_words = ['shit', 'piss', 'cunt', 'fuck']

# Define the detect_specific_words function and decorate it as a pipeline component
@Language.component("specific_word_detector")
def detect_specific_words(doc):
    has_specific_word = any(token.text.lower() in specific_words for token in doc)
    doc._.has_specific_word = has_specific_word
    return doc

# Load the spaCy English model
nlp = spacy.load("en_core_web_sm")

# Add custom attribute to Doc using extension attribute
Doc.set_extension('has_specific_word', default=False)

# Add the custom component to the spaCy pipeline using the string name
nlp.add_pipe("specific_word_detector", last=True)

# Example text
text = "This is a sample sentence containing the word dhsfdoujfsaoijfo'."

# Process the text using spaCy pipeline
doc = nlp(text)

# Access the custom attribute to check for specific words
if doc._.has_specific_word:
    print("Specific word detected!")
else:
    print("Specific word not detected.")

