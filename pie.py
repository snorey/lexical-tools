# -*- coding: utf-8 -*-

import datetime
import os
import random
import re
import threading
import time
import unicodedata
import urllib
import urllib2
from htmlentitydefs import name2codepoint
import xml.etree.cElementTree as ET

try:
	from nltk.metrics import edit_distance as distance
except:
	print "NLTK not installed, using Damerau Levenshtein"
	def distance(s1, s2): # http://www.guyrutenberg.com/2008/12/15/damerau-levenshtein-distance-in-python/
		d = {}
		lenstr1 = len(s1)
		lenstr2 = len(s2)
		for i in xrange(-1,lenstr1+1):
			d[(i,-1)] = i+1
		for j in xrange(-1,lenstr2+1):
			d[(-1,j)] = j+1
	 
		for i in xrange(lenstr1):
			for j in xrange(lenstr2):
				if s1[i] == s2[j]:
					cost = 0
				else:
					cost = 1
				d[(i,j)] = min(
							   d[(i-1,j)] + 1, # deletion
							   d[(i,j-1)] + 1, # insertion
							   d[(i-1,j-1)] + cost, # substitution
							  )
				if i and j and s1[i]==s2[j-1] and s1[i-1] == s2[j]:
					d[(i,j)] = min (d[(i,j)], d[i-2,j-2] + cost) # transposition
	 
		return d[lenstr1-1,lenstr2-1]


# -- globals and such -- #

## from WordNet.corpus.stopwords.words("english"):
stops=set(['all', 'just', 'being', 'over', 'both', 'through', 'yourselves', 'its', 'before', 'herself', 'had', 'should', 'to', 'only', 'under', 'ours', 'has', 'do', 'them', 'his', 'very', 'they', 'not', 'during', 'now', 'him', 'nor', 'did', 'this', 'she', 'each', 'further', 'where', 'few', 'because', 'doing', 'some', 'are', 'our', 'ourselves', 'out', 'what', 'for', 'while', 'does', 'above', 'between', 't', 'be', 'we', 'who', 'were', 'here', 'hers', 'by', 'on', 'about', 'of', 'against', 's', 'or', 'own', 'into', 'yourself', 'down', 'your', 'from', 'her', 'their', 'there', 'been', 'whom', 'too', 'themselves', 'was', 'until', 'more', 'himself', 'that', 'but', 'don', 'with', 'than', 'those', 'he', 'me', 'myself', 'these', 'up', 'will', 'below', 'can', 'theirs', 'my', 'and', 'then', 'is', 'am', 'it', 'an', 'as', 'itself', 'at', 'have', 'in', 'any', 'if', 'again', 'no', 'when', 'same', 'how', 'other', 'which', 'you', 'after', 'most', 'such', 'why', 'a', 'off', 'I', 'yours', 'so', 'the', 'having', 'once']) 
try:
	workingdir=os.path.dirname( os.path.realpath( __file__ ) ) # doesn't work when compiled...
except:
	workingdir="."

# -- word & user objects -- #

class Note:
	def __init__(self,text,type,sessionid):
		self.text = text
		self.type = type
		self.sessionid = sessionid
		self.type2props()
		self.showforward = False
		self.showbackward = False
		self.practiceonly = False
	
	def __str__(self):
		return self.text
	
	def __len__(self):
		return len(self.text)
	
	def type2props(self):
		if not self.type == 0:
			if not self.type % 2: 
				self.showforward = True
			if not self.type % 3: 
				self.showbackward = True
			if not self.type % 5:
				self.practiceonly = True
	
	def props2type(self):
		if (self.showforward,self.showbackward,self.practiceonly) == (False, False, False):
			self.type = 0
		else:
			self.type = 1
			if self.showforward:
				self.type = self.type * 2
			if self.showbackward:
				self.type = self.type * 3
			if self.practiceonly:
				self.type = self.type * 5
		
class Example:
	def __init__(self,text="",href="",priority=0,encoding=None,source="",parent=False):
		self.text=text
		self.priority=priority
		self.href=href
		self.encoding=encoding
		self.source=source
		self.parent=parent
		self.clue=self.testify()
	
	def testify(self,sparchar="___"):
		if self.parent is not False:
			outstring = str(self)
			mainform = self.parent.mainform.encode("utf-8")
			if mainform in outstring or mainform.capitalize() in outstring:
#				print "returning mainform"
				return outstring.replace(mainform,sparchar).replace(mainform.capitalize(),sparchar)
			else:
				for form in self.parent.inflections:
					if type(form) == unicode:
						form = form.encode("utf-8","ignore")
					if form in outstring:
						return outstring.replace(form,sparchar)
		else: 
			print "returning self"
			return str(self)
	
	def __len__(self):
		return len(self.text)
		
	def __str__(self):
		return self.encode("utf-8")
		
#	def __eq__(self,other):
#		try:
#			return bool(self.text == other.text)
#		except AttributeError:
#			return False

#	def __ne__(self,other):
#		return bool(not self.__eq__(other))
	
	def __hash__(self):
		return self.text.__hash__()
	
	def encode(self,encoding=None):
		if type(self.text) != unicode:
			return self.text
		if encoding:
			if not self.encoding:
				return self.text.encode(encoding,"ignore")
			else:
				return self.text.decode(self.encoding,"ignore").encode(encoding,"ignore")
		else:
			if not self.encoding:
				return self.text
			else:
				return self.text.decode(self.encoding,"ignore")

class Language:
	def __init__(self,name="",code=""):
		self.spaces=True
		self.name=""
		if code:
			self.name=self.code2name(code.lower())
		if not self.name:
			self.name=name
		self.superrom=False
		self.spaced=True
		self.needverblist=False
		self.getlangproperties()
	
	def __str__(self):
		return self.name
	
	def code2name(self,code):
		self.codes={"ko":"Korean"}
		try:
			return self.codes[code]
		except:
			return ""
		
	def getlangproperties(self):
		if not self.name:
			return
		if self.name=="Korean":
			self.spaced=True
			self.needverblist=True
			self.superrom=True
	
	def get_superrom(self,romanization):
		if self.name == "Korean":
			return romanization.replace("---","")
		else:
			return romanization

class User:
	def __init__(self,username="",vocabulary=False):
		self.name=username
		self.perdiem=20
		self.cycle=4
		self.chunksize=10
		self.testval=0
		self.vocabulary=vocabulary
	
	def __str__(self):
		return self.name
	
	def __len__(self):
		return len(self.name)
	
	def dumptotree(self):
		elem=ET.Element("User",{"perdiem":str(self.perdiem),"cycle":str(self.cycle),"chunksize":str(self.chunksize),"testval":str(self.testval)})
		elem.text=str(self.name)
		return elem
		
	def load(self,instring=""):
		thing=ET.XML(instring)
		self.loadfromtree(thing)
		
	def loadfromtree(self,thing): # ElementTree object
		if thing.text:
			self.name=thing.text
		for att in ["perdiem","cycle","chunksize","testval"]:
			try:
				setattr(self,att,int(float(thing.attrib[att])))
			except KeyError:
				continue


class Word:
	def __init__(self,text="",maxgloss=3,maxsample=10,user=False,language="",parent=False):
		self.maxsample=maxsample
		self.language=language
		if type(self.language) == str:
			self.language=Language(language)
		if user:
			self.user=user
		else:
			self.user=User()
		self.glossed=""
		self.glosses=[]
		self.gloss=""
		self.phonetic=u""
		self.rom=""
		self.mainform=u""
		self.examples=[]
		self.pos=""
		self.keyed=[]
		self.parent=parent
		self.inflections = set([self.mainform])
		self.tally=0 # number of occurrences in reference corpus
		self.successes=[] # number of successful learnings in current pass
		self.failures=[]
		self.history=[] # all learning events in chronological order
		self.notes=[]
		self.sequestered=False
		self.status=0 #inactive
		self.consolidations = 0
		self.paused = [] # sessions in which the word has been deliberately not considered
		if text:
			if type(text) != unicode: text=text.decode("utf-8","ignore")
			self.mainform=text.strip()
		if not self.phonetic:
			self.phonetic=self.phonetize()
		if not self.rom:
			self.rom=self.romanize()
		if self.language.superrom:
			self.superrom = self.language.get_superrom(self.rom)
		else:
			self.superrom = self.rom

	def __str__(self):
		if type(self.rom)==unicode: # just in case of weirdness...
			return self.rom.encode("utf-8","ignore")
		else:
			return self.rom
		
	def __len__(self): # a blank Word object should return false
		return len(self.mainform)
	
	def __hash__(self): # for use in sets
		try:
			key=self.mainform+self.gloss
		except:
			if type(self.mainform) != unicode:
				key=self.mainform.decode("utf-8","ignore")
			if type(self.gloss) != unicode:
				key+=self.gloss.decode("utf-8","ignore")
		if not key:
			return 0
		key=key[:20] # avoid anything crazy long
		return int("".join([str(ord(x)) for x in list(key)]))
	
#	def __eq__(self,other):
#		if hasattr(other,"mainform") and hasattr(other,"gloss"):
#			return bool(self.mainform == other.mainform and self.gloss == other.gloss)
#		else:
#			return False

#	def __ne__(self,other):
#		return not self.__eq__(other)
	
	def count(self):
		if self.parent is not False and hasattr(self.parent,"profile"):
			suxies = list(self.successes)
			thecount = 0
			pointer = 0
			for p in self.parent.profile:
				if p > 0: # positive means required to have succeeded in both directions
					for x in self.successes[pointer:]:
						pointer += 1
						if x[2] == -1:
							thecount += 1
							break
				else: # negative means only forward success is required
					for x in self.successes[pointer:]:
						pointer += 1
						if x[2] == 1:
							thecount += 1
							break
				if pointer+1 >= len(self.successes):
					break
		else: # no profile available...
			thecount = len([x for x in self.successes if x[2]==-1]) # reverse successes only
		return thecount
		
	def romanize(self): # to override
		return self.phonetic
		
	def phonetize(self):
		return self.mainform

	def succeed(self,vocab,session,is_practice=False,sessionid=0,direction=1,is_final=False,starttime=False,endtime=False):
		if session is False:
			session = vocab.session
		if not sessionid:
			sessionid = session.id
		timestamp=int(time.time())
		thenumber=(1+int(is_practice)*9)*(1+int(direction==-1))
		print thenumber # 1 for simple forward success, 2 for reverse success; 10,20 if practice
		try:
			session.todo[direction].remove(self)
		except KeyError:
			print "Hey! %s was not in todo[%s]" % (str(self),str(direction))
		if direction == 1 and not is_final: # succeeded forward, now to reverse
			session.forward_successes.add(self)
			session.todo[-1].add(self)
			print "Len todo[1], todo[-1]: ",str(len(session.todo[1])),str(len(session.todo[-1]))
		elif direction == -1:
			session.reverse_successes.add(self)
			print "Len todo[-1]: ",str(len(session.todo[-1]))
		if not is_practice:
			self.successes.append((timestamp,sessionid,direction))
		if starttime is not False and endtime is not False:
			elapsed = endtime-starttime
			self.history.append((thenumber,timestamp,sessionid,int(10.0*elapsed)))
		else:
			self.history.append((thenumber,timestamp,sessionid))
		return thenumber

	def fail(self,sessionid=0,is_practice=False,direction=1,vocab=False,session=False,starttime=False,endtime=False):
		if not vocab: 
			print "Error: no Vocabulary supplied!"
			vocab = Vocabulary()
		if session is False:
			session = vocab.session
		timestamp = int(time.time())
		thenumber = 0
		try:
			session.todo[direction].remove(self)
		except KeyError:
			print "Hey!! %s was not in todo[%s]" % (str(self),str(direction))
		if direction == 1: # succeeded forward, now to reverse
			session.forward_failures.add(self)
			if self in session.todo[-1] and not is_practice: # in case it has previously been marked as known
				session.todo[-1].remove(self)
		elif direction == -1:
			thenumber = -2
			session.reverse_failures.add(self)
		if not is_practice:
			self.failures.append((timestamp,sessionid,direction))
			self.successes = [] # restart the clock...
		if starttime is not False and endtime is not False:
			elapsed = endtime-starttime
			self.history.append((thenumber,timestamp,sessionid,int(10.0*elapsed)))
		else:
			self.history.append((thenumber,timestamp,sessionid))
		if session.is_oldcheck:
			self.status = 1
			vocab.add(self)
			vocab.session.todo[1].add(self)

	def skip(self,vocab,session=False,direction=1):
		if not session:
			session=vocab.session
		timestamp = int(time.time())
		self.history.append((-1,timestamp,session.id))
		try:
			session.todo[direction].remove(self)
		except KeyError:
			pass

	def addsample(self,sample,words,href="",priority=0):
		if isinstance(sample,basestring):
			if type(sample) == str:
				sample=sample.decode("utf-8","ignore")
			sample=Example(sample,href=href,priority=priority,parent=self)
		self.tally+=1
		if not self.keyed:
			for x in self.examples:
				simpledom=simplicity(str(x),words)
				if self.mainform in x.text:
					simpledom=simpledom*1.1 # experimental 10% bonus for exact form
				self.keyed.append((priority,simpledom,x))
		testsample=sample.text.replace(" ","")[:-1] # remove terminal punct.
		if not testsample or not isinstance(testsample,basestring):
			return False
		try:
			if testsample in " ".join([x.text.replace(" ","")[:-1] for x in self.examples]): 
				return False
		except TypeError: # no clue where this is coming from...
			return False
		if len(testsample)/len(self.mainform) < 2 and len(self.mainform) < 4: 
			return False
		elif len(testsample)-len(self.mainform) < 3: 
			return False
		elif len(testsample.replace(self.mainform,"")) < 3: 
			return False
		simpledom=simplicity(sample.text,words)
		if self.mainform in sample.text:
			simpledom=simpledom*1.1
		self.keyed.append((priority,simpledom,sample))
		self.keyed=list(set(self.keyed)) 
		self.keyed.sort()
		self.keyed.reverse()
		self.keyed=self.keyed[:self.maxsample]
		self.examples=[x[2] for x in self.keyed]
		return True

# dump to pseudo-XML
	def dumptotree(self):
		elem=ET.Element("Word",{"name":self.mainform,"status":str(self.status),"user":str(self.user),"tally":str(self.tally),"paused":",".join([str(x) for x in self.paused])})
		if self.gloss not in self.glossed:
			self.glossed = self.gloss + ", " + self.glossed
		for e in ["Romanization","Rom","Phonetic","Gloss","Glossed","Sequestered"]:
			newelem=ET.Element(e)
			try:
				newelem.text=getattr(self,e.lower())
			except AttributeError:
				continue
			if type(newelem.text) == bool:
				newelem.text=str(newelem.text)
			elem.append(newelem)
		exa=ET.Element("Examples")
		for e in self.examples:
			newelem=ET.Element("Example",{"href":e.href,"priority":str(e.priority)})
			newelem.text=e.text
			exa.append(newelem)
		elem.append(exa)
		hist=ET.Element("History")
		for h in self.history:
			if len(h) > 3:
				newelem=ET.Element("Event",{"value":str(h[0]),"session":str(h[2]),"elapsed":str(h[3])})
			else:
				newelem=ET.Element("Event",{"value":str(h[0]),"session":str(h[2])})
			newelem.text=str(h[1])
			hist.append(newelem)
		elem.append(hist)
		suxx=ET.Element("Successes")
		for s in self.successes:
			newelem=ET.Element("Event",{"value":"1","direction":str(s[2]),"session":str(s[1])})
			newelem.text=str(s[0])
			suxx.append(newelem)
		elem.append(suxx)
		notae=ET.Element("Notes")
		for n in self.notes:
			newelem=ET.Element("Note",{"type":str(n.type), "session":str(n.sessionid)})
			newelem.text=str(n)
			notae.append(newelem)
		elem.append(notae)
		inflex=ET.Element("Inflections")
		for i in self.inflections:
			newelem=ET.Element("Form")
			if type(i) == unicode:
				newelem.text = i.encode("utf-8")
			else:
				newelem.text=str(i)
			inflex.append(newelem)
		elem.append(inflex)
		return elem
	
	def load(self,instring=""):
		thing=ET.XML(instring)
		self.loadfromtree(thing)
	
	def loadfromtree(self,thing,status=-1): #ElementTree object
		self.status=int(thing.attrib["status"])
		self.mainform=thing.attrib["name"]
		try: self.tally=int(thing.attrib["tally"])
		except KeyError: pass
		try: self.paused=[int(x.strip()) for x in thing.attrib["paused"].split(",") if x]
		except KeyError: self.paused=[]
		
		for tag in ["Romanization","Rom","Gloss","Glossed","Sequestered"]:
			if thing.findtext(tag) is not None:
				setattr(self,tag.lower(),thing.findtext(tag))
		if self.glossed and not self.gloss:
			self.gloss=self.glossed.split(";")[0].split(",")[0]
		elif self.gloss and not self.glossed:
			self.glossed=self.gloss
		if self.sequestered=="False":
			self.sequestered=False
		else:
			self.sequestered=bool(self.sequestered)
		try:
			self.rom=self.romanization
		except AttributeError:
			self.romanization=self.rom
		self.superrom = self.language.get_superrom(self.rom)
		history=list(thing.find("History"))
		for h in history:
			if "elapsed" in h.attrib.keys():
				self.history.append((int(h.attrib["value"]),int(float(h.text)),int(float(h.attrib["session"])),int(float(h.attrib["elapsed"])))) # h.text is timestamp
			else: 
				self.history.append((int(h.attrib["value"]),int(float(h.text)),int(float(h.attrib["session"])))) # h.text is timestamp

		successes=list(thing.find("Successes"))
		for s in successes:
			timestamp=float(s.text)
			session=float(s.attrib["session"])
			try: direction=int(s.attrib["direction"])
			except KeyError: direction=1
			self.successes.append((timestamp,session,direction))
		examples=list(thing.find("Examples"))
		for e in examples:
			if not e.text: continue
			newexample=Example(e.text.strip(),parent=self)
			for a in ["href"]:
				if a in e.attrib.keys():
					setattr(newexample,a,e.attrib[a])
			for a in ["priority"]:
				if a in e.attrib.keys():
					setattr(newexample,a,int(e.attrib[a]))
			newexample.priority=int(newexample.priority)
			self.examples.append(newexample)
		inflections = list(thing.find("Inflections"))
		self.inflections = set()
		for i in inflections:
			if not i.text: continue
			self.inflections.add(i.text.strip())
	
	def getstars(self):
		outstring=""
		for s in self.successes:
			if s[2] < 0: #reverse success
				outstring+=u"\u2605" # solid star
			else:
				outstring+=u"\u2606" # empty star
		return outstring
	
	def addnote(self,text="",session=time.time(),type=""):
		note = Note(text=text,session=session,type=int(type))
		note.user = user
		self.notes.append(note)

	def show_history(self):
		outstring=""
		historyback=list(self.history)
		historyback.reverse()
		for h in historyback:
			outstring+="\t".join([datetime.datetime.min.fromtimestamp(h[1]).isoformat()[:-3],code2english(h[0])])+"\r\n"
		return outstring

# -- lexicon objects -- #
class MetaVocab:
	def __init__(self,language="",filepath="",newwords=[],user=User(""),restorefrom="D:\\statusfile.txt",dummy=False):
		self.user=user
		self.username=str(user)
		words=set(newwords)
		self.words=list(words)
		self.allwords=set(self.words)
		status=(0,0,0)
		self.current_word=Word()
		self.current_text=""
		self.done=set()
		self.can_assess=True
		
	def load(self):
		pass

class Group(MetaVocab):
	def __init__(self,maxsize=0,members=set(),tooclose=0.35,language="",filepath="",newwords=[],user=User(""),restorefrom=""):
		MetaVocab.__init__(self,language=language,filepath=filepath,newwords=newwords,user=user,restorefrom=restorefrom)
		self.allwords|=members
		self.words.extend(list(members))
		self.romanizations=set([x.rom for x in self.words])
		self.glosses=set()
		self.wordcloud=set()
		self.max=maxsize
		self.tooclose=tooclose # minimum edit distance between members as divided by word length
		self.storage=set()
		self.bigglom=self.glom(self.romanize())
		self.bigglom += " "+self.glom(self.get_glosses())
		
	def get_glosses(self):
		glosses=set()
		for w in self.words:
			glosses |= set(w.glosses)
		return glosses
		
	def glom(self,argument=[]):
		if not argument:
			argument=[x.mainform for x in self.words]
		glomstring=" ".join(list(argument))
		return glomstring
	
	def romanize(self):
		self.romanizations=set([x.rom for x in self.words])
		return self.romanizations
		
	
	def ok2add(self,word,definition="",proceed=False,biglist=[],maxoverlap=1,worry_about_length=True,roman=False):
		if self.max and len(self.words) >= self.max and worry_about_length:
			return False
		if not definition:
			definition=word.gloss
		stringword=word.mainform
		if not roman:
			romword=word.superrom
		else:
			romword=roman
		bigglom=self.bigglom
		if stringword in bigglom: #in case there is already a longer word/phrase containing this
			print "mainform in glom ", stringword
			return False
		elif romword in bigglom: # updating self.romanizations
			print "rom in glom ", romword
			return False
		elif definition in bigglom:
			print "def in glom", definition
			return False
		elif len(word.glosses) > 1:
			for gloss in word.glosses:
				if gloss in bigglom:
					print "gloss in glom", gloss
					return False
		if len(romword) > 4:
			pieces = [romword[x:x+4] for x in range(0,len(romword)-3)]
			pieces = [x for x in pieces if x in bigglom]
			if pieces:
				print "overlapping pieces", romword, str(pieces)
				return False
		if len(definition) > 5:
			pieces = [definition[x:x+5] for x in range(0,len(definition)-4)]
			pieces = [x for x in pieces if x in bigglom]
			if pieces:
				try: 
					print "overlapping pieces", definition, str(pieces)
				except UnicodeEncodeError:
					pass
				return False
		closes = [y for y in [
				(x,romword,1.8*distance(x,romword)/len(romword+x)) 
					for x in self.romanizations
				] if y[2] < self.tooclose]
		if closes:
			print "close matches", romword,str(closes)
			return False
		if definition and maxoverlap:
				cloud=wordcloud(definition)
				if len(cloud.intersection(self.wordcloud)) >= maxoverlap:
					print "max overlap"
					return False
		return True

	def add(self,word,definition,tupled=False):
		self.romanizations.add(word.rom)
		self.words.append(word)
		random.shuffle(self.words)
		self.allwords.add(word)
		self.glosses.add(definition)
		self.wordcloud |= wordcloud(definition)
		self.bigglom += " "+word.rom+" "+word.glossed
		if tupled:
			self.storage.add(tupled)
		
class Vocabulary(MetaVocab):
	def __init__(self,language="",newwords=[],user=User(""),restorefrom="",is_practice=False,startnewsession=False,filter=True):
		MetaVocab.__init__(self,language=language,newwords=newwords,user=user,restorefrom=restorefrom)
		words = set(newwords)
		self.words = list(words)
		self.wordsforward = list(words)
		self.wordsreverse = []
		self.is_practice = is_practice
		self.language = language
		self.user = user
		self.goal = 1000
		self.allwords = set(self.words)
		self.path = ""
		self.session = Session(self)
		self.quickfind = {}
		self.readings = []
		self.profile = [1, 1, 2, 3, -5, -8, -13]
		self.words_saved = False # to be used only when it is necessary to temporarily displace the wordslist
		if restorefrom:
			self.path = restorefrom
			self.load(open(restorefrom).read())
		if startnewsession:
			self.newsession(0)
		if filter and not self.session: # don't filter if session is in progress.
			status = str(self.filter(thecap=self.user.cycle))
			print "Vocab start status:",status
		else:
			self.words = [x for x in self.allwords if x.status==1]
		try:
			self.current_word = self.words[0]
		except IndexError:
			self.current_word = Word()
		self.session.todo[1] = set(self.words)
		self.quickfind = dict([(x.rom,x) for x in self.allwords])
		print "Done creating vocabulary"

	def __iter__(self):
		return iter(self.words)
	
	def __len__(self):
		return len(self.words)
		
	def __str__(self):
		return str(self.current_word)
		
	def __getitem__(self,index):
			return self.words[index]
		
	def __setitem__(self,index,item):
		self.words[index]=item
		
	def index(self,item=False):
		if not item:
			item=self.current_word
		return self.words.index(item)
		
	def run(self,output="gui"):
		if output=="gui":
			import wx, pie_crust
			app=wx.App(False)
			form=pie_crust.ManagerWindow(vocab=self)
			form.Show()
			app.MainLoop()
			del(app)
		elif output=="web": # to do
			pass

	def filter(self,thecap=-1,maxnew=0,maxgroup=0,input=[],reviewgap=600000,prevsession=0): 
# wherein the words to be actively reviewed in the current session are separated
		review=0
		new=0
		self.consolidations = 0
		if thecap == -1: # default: use user values
			thecap=self.user.cycle # number of consecutive successes needed
		if not maxgroup:
			maxgroup=int(self.user.perdiem*self.user.cycle*1.5) # allow some accumulation, but not a completely insane amount
			if maxnew+len(self.words) >= maxgroup:
				maxgroup=maxnew+len(self.words)
		self.words=[]  #reset pool of available words
		available=[((1+len(x.successes))*x.tally,x) for x in self.allwords if x.status==1]
		unavailable=[(x.tally,x) for x in self.allwords if x.status < 1]  #sequestered, not yet active, etc.
		print "maxgroup,maxnew "+str(maxgroup),str(maxnew)
		thegroup=Group(maxsize=maxgroup)
		available.sort()
		available.reverse() # in case of conflict, privilege more-learned and more-frequent
		available=[x[1] for x in available]
		print "# Available words: "+str(len(available))
		for w in available:
			if not w.gloss: # no translation available
				continue
			elif w.successes:
				if w.count() < len(self.profile): # still to do
					if self.session.id in w.paused: # glitchy repeat?
						continue 
					elif len(w.paused)+1 < abs(self.profile[w.count()]):
						w.paused.append(self.session.id)
						if len(w.paused) < 2 or len(w.paused)+2 >= abs(self.profile[w.count()]):
							thegroup.add(w,w.glossed) # keep hackles up even if word is temporarily out of circ
						print "Pausing "+w.rom
						continue
				else: # all done
					w.status = -1 
					self.consolidations += 1
					self.session.consolidated.add(w)
					continue
			if thegroup.ok2add(w):
				self.add(w)
				thegroup.add(w,w.glossed)
			else:
				w.status=0
		print "# Unavailable words: "+str(len(unavailable))
		unavailable.sort()
		unavailable.reverse()
		unavailable=[x[1] for x in unavailable]
		if maxnew: # skip this whole business if no maxnew supplied, e.g. when reloading vocab.
			print "Filtering...",str(len(unavailable))
			for w in unavailable:
				if maxnew and new >= maxnew:
					print "reached maxnew: ",str(new)
					break
				elif w.sequestered:
					seqs=[x for x in w.history if x[0] in [100,200,400]]
					print "Sequestered",str(w.sequestered),w.rom
					if seqs:
						if time.time()-seqs[-1][2] < reviewgap: # has the allotted time elapsed?
							print "insufficient time elapsed: "+str(time.time()-seqs[-1][2])+" "+w.rom
							continue
						else:
							w.sequestered=False # unseq, but don't assimilate until next session
							
					else: # slipped through cracks?
						w.history.append((100,self.session.id,time.time()))
						continue
				elif w.status == 0: #inactive
					dels=[x for x in w.history if x[0]==-100]
					if dels: # has been deleted
						print "deleted",w.rom
						continue
				if thegroup.ok2add(w): # if we're still here, time to see if this one fits.
					if w.status == 0 and not w.sequestered and not w.successes: 
						if prevsession and str(prevsession) not in str(w.history):
							new += 1
							print "added new: "+w.rom
					else: 
						review += 1
					thegroup.add(w,w.glossed)
					self.activate(w)
		random.shuffle(self.words)
		try:
			self.current_word=self.words[0]
		except IndexError:
			pass
		self.getstats()
		return (new,review,len(self.words),len(self.allwords))
		
	def review_old(self,limit=0,reviewgap=600000): # gather up a bunch of words eligible for further review...
# reviewgap: min. wait time for sequestered words (default ~1 week)
		ranks=[]
		if not limit:
			limit=int(0.5*self.user.perdiem)
		# for each word: has enough time elapsed?
		candidates=set([x for x in self.allwords if x.status==-1 and x.successes])
		print "Checking %s graduated words." % str(len(candidates))
		thegroup=Group(members=set(self.words))
		if self.language=="Korean":
			thegroup.tooclose=0.15 # correct for effects of our house romanization
		# check all for availability, time elapsed
		for w in candidates:
			if w.consolidations > 2: #i.e. has been consolidated and reviewed at least twice
				w.status=-2
				continue
			if not thegroup.ok2add(w):
				print "not OK"
				continue
			gap=int(time.time()-w.successes[-1][0])
			if gap < reviewgap*w.consolidations: 
				continue
			thegroup.add(w)
			ranks.append((gap,w))
		# rank by timeliness ... the longer it's been out, the more urgent to review
		print len(ranks)
		ranks.sort()
		ranks.reverse()
		ranks=ranks[:limit]
		outwords=[x[1] for x in ranks]
		return outwords

	def dump(self):
		import xml.etree.ElementTree as ET
		thing=ET.Element("Vocabulary",attrib={"language":str(self.language),"goal":str(self.goal),"lastsession":str(self.session.id)})
		thing.append(self.user.dumptotree())
		thing.append(self.session.dumptotree())
		for w in self.allwords:
			thing.append(w.dumptotree())
		for r in self.readings:
			elem = ET.Element("Reading")
			elem.text = str(r.id)
		indent(thing)
		return ET.tostring(thing,encoding="utf-8")

	def save(self,filepath=""):
		if not filepath:
			filepath=self.path
# backup
		backpath=filepath.replace(".txt","_backup.txt")
		if not backpath.endswith(".txt"):
			backpath+="_backup"
		try: 
			backfiletext = open(filepath).read()
			backfilehandle = open(backpath,"w")
			with backfilehandle:
				backfilehandle.write(backfiletext)
		except IOError:
			pass
		outstring=self.dump()
		outfile=open(filepath,"w")
		with outfile:
			outfile.write(outstring)
		return True
	
	def loadfile(self,filepath="",encoding="utf-8",wordclass=Word):
		thefile = open(filepath).read()
		self.path=filepath
		try:
			self.load(thefile,encoding,wordclass)
			print len(self)
			return True
		except Exception:
			print "Fail"
			return False
			
	def load(self,instring="",encoding="utf-8",wordclass=Word): 
		print len(instring)
# load core data
		thing=ET.XML(instring)
		if thing.tag != "Vocabulary":
			print "Bad XML file."
			return False
		attrs=["language","goal","lastsession"]
		for a in attrs:
			try:
				setattr(self,a,thing.attrib[a])
			except KeyError:
				continue
		self.language=Language(self.language)
		self.goal=int(self.goal)
		tags=list(thing)
# and now everything else...
		session=False
		for t in tags:
			if t.tag=="User":
				self.user.loadfromtree(t)
			elif t.tag=="Word":
				word=Word(parent=self)
				word.language=self.language
				word.loadfromtree(t)
				self.allwords.add(word)
			elif t.tag=="Session":
				session=t
			elif t.tag == "Reading":
				self.readings.append(t.text)
			else: 
				print "Unrecognized tag: ",t.tag
# NB: because Session.loadfromtree() uses vocab.quickfind(), this needs to come after words have been loaded.
		if session:
			self.session.loadfromtree(t,self.quickfind)
		print "Getting stats..."
		self.getstats()
		return True
		
	def undo(self,session=False,direction=1):
		if self.index()==0: 
			return False
		word=self.current_word
		if session==False:
			session=self.session
		if not word.history:
			return False
		if direction==1:
			try: 
				session.todo[-1].remove(word)
			except KeyError:
				pass
		this=word.history[-1]
		if this[0] == 1:
			word.successes=word.successes[:-1]
		word.history=word.history[:-1]
		return True
	
	def sequester(self,word,newstatus=0):
		if word.history:
			if word.history[-1][0] == 100:
				return False
		word.history.append((100,self.session.id,time.time()))
		word.sequestered=True
		word.status=newstatus
		self.session.practiced.add(word)
		try:
			self.words.remove(word)
		except:
			print "Unable to remove "+word.rom
		for t in [1,-1]: # zombie killer
			if word in self.session.todo[t]: self.session.todo[t].remove(word)
		return word
		
	def delete(self,word):
		if word.status==0 and word.sequestered==True and word.history and word not in self.words:
			if word.history[-1][0] == -100:
				return False # already deleted
		word.history.append((-100,self.session.id,time.time()))
		word.sequestered=True
		word.status=0
		if word in self.words:
			print "deleting..."
			self.words.remove(word)
		return True
	
	def getstats(self):
		doneish = [x for x in self.allwords if len([y for y in x.successes if y[2]==-1])>=self.user.cycle]
		for d in doneish:
			if d.sequestered is not True and d.status > -1:
				self.sequester(d,newstatus=-1)
		incoming = [x for x in self.words if len(x.successes) == 0]
		seqs = [x for x in self.allwords if x.sequestered] # check use of sequestered bit
		deleteds = [x for x in self.allwords if x.status ==0 and "-100," in str(x.history)]
		self.done = set([x for x in self.allwords if x.status == -1])
		self.activecount = len([x for x in self.allwords if x.status==1])
		known = set([x for x in self.allwords if x.status == 1 and x.successes])
		known |= set([x for x in self.allwords if x.status == -1 and x.successes])
		self.knowncount = len(known)
		self.session.update_stats()
		if not self.session.forward_total: # i.e. only if count is still at its default value of 0
			self.session.forward_total = self.activecount
		if len(self.words)>self.activecount: # this *shouldn't* be necessary
			self.activecount = len(self.words)
		if not self.session.reverse_total:
			self.session.reverse_total = len(self.session.todo[-1])
		self.sequesteredcount = len(seqs)
		self.deletedcount = len(deleteds)
		self.donecount = len(self.done)
		self.incomingcount = len(incoming)
		self.learningcount = self.activecount+self.donecount
		return (self.activecount,self.learningcount)
	
	def add(self,word):
		self.allwords.add(word)
		self.words.append(word)
		self.quickfind[word.rom]=word
		return True
			
	def activate(self,word):
		self.words.append(word)
		word.status=1
		return True
	
	def newsession(self,daysworth=-1):
		prevsession = int(self.session.id)
		print "creating new session",str(self.session.id),str(int(time.time()))
		if daysworth==-1: #default to user pref
			daysworth=self.user.perdiem
		if self.allwords:
			prewords = set(self.words)
			self.filter(maxnew=daysworth,prevsession=prevsession)
			print "new len words: "+str(len(self.words))
			postwords = set(self.words)
			self.newthistime = prewords - postwords
		else:
			print "Allwords not found: "+str(len(self.allwords))
		self.session.todo[1]=set(self.words)
		try:
			self.current_word=list(self.session.todo[1])[0]
		except IndexError:
			self.current_word=Word()
		self.session=Session(self)
		foo=self.getstats()
		print "Done creating session.",str(foo)
		return True
			
	def reset(self): # destroy all learning data
		self.words=[]
		for a in self.allwords:
			a.status=0
			a.history=[]
			a.successes=[]
		print len(self.allwords)
		self.newsession(0)
		self.save()
		
	def bands(self,bandsize=500):
		if len(self.allwords) <= bandsize:
			return [self.allwords]
		if len(set(x.tally for x in self.allwords)) == 1:
			return [self.allwords]
		sortable=[(x.tally,x) for x in self.allwords]
		sortable.sort()
		sortable.reverse()
		sorted=[x[1] for x in sortable]
		breaker=0
		banded=[]
		while breaker < len(self.allwords):
			banded.append((breaker+bandsize,set(sorted[breaker:breaker+bandsize])))
			breaker+=bandsize
		return banded #list of (int,set) tuples, with set comprising ALL words in band
	
class Session:  #information on one learning day
	def __init__(self,vocabulary,id=time.time(),is_practice=False,justnew=False,is_oldcheck=False):
		if not is_practice:
			is_practice = vocabulary.is_practice
		self.is_practice = is_practice
		self.is_oldcheck = is_oldcheck
		self.id = int(id)
		self.language = vocabulary.language
		self.user = vocabulary.user
		if justnew:
			self.cap = self.user.cycle*int(not self.is_practice) # if practice session, only 0s
		else:
			self.cap = self.user.cycle
		self.vocabulary = vocabulary
		try:
			self.vocabulary.current_word = self.vocabulary.words[0]
		except IndexError:
			pass
		self.forward_successes = set()
		self.reverse_successes = set()
		self.forward_failures = set()
		self.reverse_failures = set()
		self.practiced = set()
		self.consolidated = set()
		self.todo = {}
		self.todo[1] = set() # dynamic set of words awaiting forward review
		self.todo[-1] = set() # dynamic set of words that have passed forward review and await reversal
		self.redo =set() # set of (direction,word) tuples
		try:
			self.forward_total = self.vocabulary.activecount # static count of total words for forward review
		except AttributeError:
			self.forward_total = 0
		self.reverse_total = 0
		self.redoing = False
		self.newbies = set([x for x in vocabulary.words if len(x.successes) == 0])
		self.newthistime = set() # words started in this session
		self.oldthistime = set() # words finished in this session

	def __len__(self): # primary purpose: return 0/False if no action yet
		return len(self.forward_successes|self.reverse_successes|self.forward_failures|self.reverse_failures|self.todo[1]|self.todo[-1])
	
	def update_stats(self): # to be called by Vocabulary.getstats()
		if not self.todo[1] and not self.forward_total: # forward_total check to avoid triggering when set has been emptied
			self.todo[1] = set(self.vocabulary.words)
			self.forward_total = self.vocabulary.activecount
# clear out any sludge that has crept in
		self.todo[1] -= self.forward_successes
		self.todo[-1] -= self.reverse_successes
		print "Updating Session stats: ",str(len(self.todo[1])),str(self.forward_total)
		if not self.newbies: # static set, but dependent on vocab filtering, so update only if not already created.
			self.newbies = set([x for x in self.vocabulary.words if len(x.successes) == 0])
		if not self.forward_total:
			self.forward_total = len(self.todo[1])
			
		def update_static_stats(self):
			self.newbies = set([x for x in self.vocabulary.words if len(x.successes) == 0])

	def dumptotree(self):
		elem=ET.Element("Session",{"id":str(self.id),"user":str(self.user),"language":str(self.language)})
		successes1=ET.Element("Successes",{"direction":"+1","count":str(len(self.forward_successes))})
		successes2=ET.Element("Successes",{"direction":"-1","count":str(len(self.reverse_successes))})
		for s in self.forward_successes:
			newelem=ET.Element("Success",{"direction":"+1"})
			newelem.text=str(s)
			successes1.append(newelem)
		for s in self.reverse_successes:
			newelem=ET.Element("Success",{"direction":"-1"})
			newelem.text=str(s)
			successes2.append(newelem)
		failures1=ET.Element("Failures",{"direction":"+1","count":str(len(self.forward_successes))})
		failures2=ET.Element("Failures",{"direction":"-1","count":str(len(self.reverse_successes))})
		for s in self.forward_failures:
			newelem=ET.Element("Failure",{"direction":"+1"})
			newelem.text=str(s)
			failures1.append(newelem)
		for s in self.reverse_failures:
			newelem=ET.Element("Failure",{"direction":"-1"})
			newelem.text=str(s)
			failures2.append(newelem)
		todo1=ET.Element("Todo",{"direction":"+1","total":str(self.forward_total)})
		todo2=ET.Element("Todo",{"direction":"-1","total":str(self.reverse_total)})
		for d in [1,-1]:
			for t in self.todo[d]:
				newelem=ET.Element("Wordup")
				newelem.text=str(t)
		for e in [successes1,successes2,failures1,failures2,todo1,todo2]:
			elem.append(e)
		return elem
	
	def loadfromtree(self,thing,quickfind):
		for att in ["id","user","language"]:
			try:
				setattr(self,att,thing.attrib[att])
			except KeyError:
				continue
		successes = thing.findall("Successes")
		for s in successes:
			if "direction" not in s.attrib.keys(): continue
			elif s.attrib["direction"] == "+1":
				self.forward_success = int(s.attrib["count"])
				self.forward_successes = set(self.vocabulary.quickfind[x.text] for x in list(s))
			elif s.attrib["direction"] == "-1":
				self.reverse_success = int(s.attrib["count"])
				reverseok = list(s)
				self.reverse_successes = set(self.vocabulary.quickfind[x.text] for x in list(s))
		failures=thing.findall("Failures")
		for s in failures:
			if s.attrib["direction"] == "+1":
				self.forward_failure = int(s.attrib["count"])
				self.reverse_failures = set(self.vocabulary.quickfind[x.text] for x in list(s))
			elif s.attrib["direction"] == "-1":
				self.reverse_failure = int(s.attrib["count"])
				self.reverse_failures = set(self.vocabulary.quickfind[x.text] for x in list(s))
		todoes = thing.findall("Todo")
		for t in todoes:
			if t.attrib["direction"] == "+1":
				self.forward_total = int(t.attrib["total"])	
			if t.attrib["direction"] == "-1":
				self.reverse_total = int(t.attrib["total"])
			direction = int(t.attrib["direction"])
			wordups = t.findall("Wordup")
			for w in wordups:
				word = self.vocabulary.quickfind[w.text]
				self.todo[direction].add(word)
				word.status = 1

	def load(self,instring="",quickfind={}):
		thing = ET.XML(instring)
		self.loadfromtree(thing)
		
	def getdone(self,direction=1,check=True): # returns set of all words tested during current session, optionally removing those no longer in active review
		if direction == 1:
			thelist = self.forward_successes | self.forward_failures
		else:
			thelist = self.reverse_successes | self.reverse_failures
		if check:
			thelist = thelist.intersection(set(self.vocabulary.words))
		return thelist


# -- End of class definitions -- #

# miscellaneous utility functions

def wordcloud(definition): #generates a cloud of associated words from a definition string
		words=set(re.findall("[a-zA-Z\-]+",definition))-stops
		synsets=[]
		cloud=set()
		return words

		
def revalidate(words): #utility to clean up examples when updating code
	for w in words:
		proxy=Word() # blank word for dummy testing
		proxy.mainform=w.mainform
		proxy.examples=list(w.examples)
		examples=list(w.examples)
		for e in set(examples):
			try:
				proxy.examples.remove(e)
				proxy.addsample(e,words)
				print "OK ",w.rom
			except:
				print "Error! ",w.rom
		w.examples=list(proxy.examples)
		
def unescape(text): 
#From code by Fredrik Lundh at http://effbot.org/zone/re-sub.htm#-html
# Licensed to the public domain at http://effbot.org/zone/copyright.htm
# Seems to work better than BeautifulSoup for this purpose
	def fixup(m):
		text = m.group(0)
		if text[:2] == "&#":
			try:
				if text[:3] == "&#x":
					return unichr(int(text[3:-1], 16))
				else:
					return unichr(int(text[2:-1]))
			except ValueError:
				pass
		else:
			try:
				text = unichr(name2codepoint[text[1:-1]])
			except KeyError:
				pass
		return text
	return re.sub("\&\#?\w+\;", fixup, text)

def get_frequencies(text,already={}):
	tokens=tokenize(text)
	for t in set(tokens):
		if t in already.keys():
			already[t]+=tokens.count(t)
		else:
			already[t]=tokens.count(t)
	return already

def tokenize(text,tokenizer=False):
	if tokenizer:
		return tokenizer.tokenize(text)
	else:
		return re.findall("[A-Za-z\'\-]+",text)

def get_sentences(text):
	enders=[u"¡£",u"£¿",u"£¡",u". ",u"?",u"!"]
	for e in enders:
		text=text.replace(e,e+"|||")
	text=text.replace(u"\n",u"\n|||")
	lines=[x.strip() for x in text.split("\n") if x.count("|||")>1]
	newtext="\n".join(lines)
	sentences=text.split(u"|||")
	sentences=[x.strip() for x in sentences if x.strip()]
	sentences=[x for x in sentences if x[-1] in enders]
	return sentences

def process_sentences(allforms,allsorted,allwords,newsentences,wiki=False):
	for n in newsentences:
		if len(n) > 15: continue
		if wiki:
			n=clean_text_wiki(n) # scrub initial *, #, etc.
		theseforms=set([x for x in allforms if x in n])
		if not theseforms: continue
		for w in theseforms:
			if segmenter.tokenize(w)[0] in segmenter.tokenize(n): #final sanity check
				allsorted[w].addsample(n,allwords)

def simplicity(sentence,wordset):
	if not sentence.strip(): return 0
	allforms=set()
	for w in wordset:
		allforms|=w.inflections
	oldlength=len(sentence)
	for a in allforms:
		if not a: continue
		try:
			if type(a) == str: 
				a=a.decode("utf-8","ignore")
		except UnicodeDecodeError:
			print "Exception decoding!"
		else:
			if a in sentence: 
				sentence=sentence.replace(a," ")
	sentence=sentence.replace(" ","")
	newlength=len(sentence)
	simplicity=100*(float(oldlength-newlength)/float(oldlength) ** 1.5) # slight penalty for length
	return simplicity

def code2english(code):
	if code==1: return "win"
	elif code==-1: return "skipped"
	elif code==0: return "fail"
	elif code==2: return "win -- reverse"
	elif code==-2: return "fail -- reverse"
	elif code==10: return "win -- practice"
	elif code==100: return "sequestered"
	elif code==-100: return "deleted"
	elif code==200: return "sequestered -- auto"
	elif code==400: return "already known"
	else: return str(code)
	
class Library:
	def __init__(self):
		self.id=int(time.time())
		self.readings=set()
		
	def __str__(self):
		return str(self.id)

class Course:
	def __init__(self,vocab=Vocabulary(),user=User(),language=Language(),library=Library()):
		self.vocab=vocab
		self.user=user
		self.language=language
		self.library=library
	
class Reading:
	def __init__(self,text="",vocab=Vocabulary(),
	language=Language(),user=User(),path="",title="",
	id=time.time(),library=Library(),analysis=False):
		self.id=int(time.time())
		self.language=language
		self.user=user
		self.location=""
		self.title=title
		if not self.title.strip():
			self.title=str(self.id)
		self.vocab=vocab
		self.library=library
		self.profiles={}
		for att in ["language","user"]:
			if not getattr(self,att):
				setattr(self,att,getattr(self.vocab,att))
		self.text=text
		self.lastupdate=int(time.time())
		if analysis is not False:
			self.enable_analysis()
		
	def enable_analysis(self):
		global lib
		tt = threading.Thread(target=langport,args=(self.language,))
		tt.start()

	def __str__(self):
		return str(self.id)
		
	def dump(self):
		import xml.etree.ElementTree as ET
		elem=ET.Element("Reading",
			{"language":str(self.language),
			"user":str(self.user),
			"vocab":str(self.vocab),
			"library":str(self.library),
			"id":str(self.id),
			"title":str(self.title),
			"location":str(self.location),
			"lastupdate":str(self.lastupdate),
			})
		elem.text=self.text
		try:
			profile=[x for x in self.profiles["frequency"].keys()]
		except KeyError:
			pass
		else:
			prolem=ET.Element("Profile",{"type":"frequency"})
			for p in profile:
				wordlem=ET.Element("Wordup",{"tally":str(self.profiles["frequency"][p])})
				wordlem.text=p
				prolem.append(wordlem)
			elem.append(prolem)
		indent(elem)
		return ET.tostring(elem,encoding="utf-8")
		
	def load(self,xml=""):
		thing=ET.XML(xml)
		if thing.tag != "Reading":
			print "Bad XML file."
			return False
		attrs=["language","user","vocab","library","id","title","location","lastupdate"]
		for a in attrs:
			try:
				setattr(self,a,thing.attrib[a])
			except KeyError:
				continue
		self.text=thing.text
		
	def process(self,callme=False,param=False):
		global lib
		if type(self.text)==str:
			self.text=self.text.decode("utf-8","ignore")
		profile = lib.frequentize(self.text,vocab=self.vocab,callme=callme,param=param)
		self.profiles["frequency"] = profile
		return profile
	
	def target(self,level=0.95,prefervocab=True,onlyvocab=False):
		try:
			profile=self.profiles["frequency"]
		except KeyError:
			print "getting frequency profile"
			profile=self.process()
		total=sum(profile.values()) # total number of processed words
		targeted=0.0
		freqs=[(profile[x],x) for x in profile.keys()]
		freqs.sort()
		freqs.reverse()
		unpreferred=[]
		
		dothese=[]
		key=0
		while targeted/total < level:
			try:
				if prefervocab and freqs[key][1] not in self.vocab.quickfind.keys():
					unpreferred.append(freqs[key])
				else:
					targeted+=freqs[key][0]
					dothese.append(freqs[key][1])
			except IndexError:
				print "Index error."
				if key >= len(freqs) and not onlyvocab:
					subkey=key-len(freqs)
					targeted+=unpreferred[subkey][0]
					dothese.append(unpreferred[subkey][1])
				else:
					break
			key+=1
		print targeted/total
		self.dothese=dothese
		return dothese

def langport(language):
	global lib
	print "importing "+str(language)
	if str(language)=="Korean":
		import kore3 as lib
	elif str(language)=="Japanese":
		import japa as lib
	elif str(language)=="Indonesian":
		import indo as lib

def indent(elem, level=0): # Code from Effbot.org
	i = "\n" + level*"  "
	if len(elem):
		if not elem.text or not elem.text.strip():
			elem.text = i + "  "
		if not elem.tail or not elem.tail.strip():
			elem.tail = i
		for elem in elem:
			indent(elem, level+1)
		if not elem.tail or not elem.tail.strip():
			elem.tail = i
	else:
		if level and (not elem.tail or not elem.tail.strip()):
			elem.tail = i

if __name__ == "__main__" :
	import sys
	import pie_crust
	outfile=open("latest_log.txt","a")
	sys.stdout=outfile
	sys.stderr=outfile
	print "STARTUP: " +datetime.datetime.today().isoformat()
	pie_crust.run3()
	
