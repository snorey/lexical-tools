# -*- coding: utf-8 -*-

import os, re
import datetime, time
import urllib2, urllib
import unicodedata, random
from htmlentitydefs import name2codepoint

# -- Third-party modules -- #
import wx
import wx.lib.agw.piectrl
import wx.lib.scrolledpanel
from wx.html import HtmlWindow

# from nltk.corpus import wordnet as wn -- has to go server-side
from nltk.metrics import edit_distance as distance

import matplotlib
matplotlib.interactive( True )
matplotlib.use( 'WXAgg' )

# -- globals and such -- #

wordmatcher='(?<=\W)[a-z][a-z\-]+[a-z](?=\W)'
wx.SetDefaultPyEncoding("utf-8")

## from WordNet.corpus.stopwords.words("english"):
stops=set(['all', 'just', 'being', 'over', 'both', 'through', 'yourselves', 'its', 'before', 'herself', 'had', 'should', 'to', 'only', 'under', 'ours', 'has', 'do', 'them', 'his', 'very', 'they', 'not', 'during', 'now', 'him', 'nor', 'did', 'this', 'she', 'each', 'further', 'where', 'few', 'because', 'doing', 'some', 'are', 'our', 'ourselves', 'out', 'what', 'for', 'while', 'does', 'above', 'between', 't', 'be', 'we', 'who', 'were', 'here', 'hers', 'by', 'on', 'about', 'of', 'against', 's', 'or', 'own', 'into', 'yourself', 'down', 'your', 'from', 'her', 'their', 'there', 'been', 'whom', 'too', 'themselves', 'was', 'until', 'more', 'himself', 'that', 'but', 'don', 'with', 'than', 'those', 'he', 'me', 'myself', 'these', 'up', 'will', 'below', 'can', 'theirs', 'my', 'and', 'then', 'is', 'am', 'it', 'an', 'as', 'itself', 'at', 'have', 'in', 'any', 'if', 'again', 'no', 'when', 'same', 'how', 'other', 'which', 'you', 'after', 'most', 'such', 'why', 'a', 'off', 'I', 'yours', 'so', 'the', 'having', 'once']) 
try:
	workingdir=os.path.dirname( os.path.realpath( __file__ ) ) # doesn't work when compiled...
except:
	workingdir="."

class Nullity:
	pass

# -- word & user objects -- #
class Example:
	def __init__(self,text="",href="",priority=0,encoding=None,source=""):
		self.text=text
		self.priority=priority
		self.href=href
		self.encoding=encoding
		self.source=source
	
	def __len__(self):
		return len(self.text)
		
	def __str__(self):
		return self.encode("utf-8")
		
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
		self.language=""
		if code:
			self.name=self.code2name(code.lower())
		if not self.language:
			self.name=name
		self.getlangproperties(self.language)
	
	def __str__(self):
		return self.name
	
	def code2name(self,code):
		self.codes={"ko":"Korean"}
		try:
			return self.codes[code]
		except:
			return ""
		
	def getlangproperties(self,name):
		if not name:
			return
		if name=="Korean":
			self.spaced=True
			self.needverblist=True

class User:
	def __init__(self,username="",vocabulary=False):
		self.name=username
		self.perdiem=20
		self.cycle=4
		self.chunksize=10
		self.vocabulary=vocabulary
	
	def __str__(self):
		return self.name
	
	def __len__(self):
		return len(self.name)
	
	def dump(self,indented="\t",singleindent="\t",encoding="utf-8"):
		outstring=indented+'<User perdiem="%s" cycle="%s" chunksize="%s">%s</User>\n' % (self.perdiem,self.cycle,self.chunksize,self.name)
		return outstring
		
	def load(self,instring=""):
		text=instring.split("<User")[1].split("</User>")[0]
		self.perdiem=int(text.split('perdiem="')[1].split('"')[0])
		self.cycle=int(text.split('cycle="')[1].split('"')[0])
		try:
			self.chunksize=int(text.split('chunksize="')[1].split('"')[0])
		except IndexError:
			pass
		self.name=text.split(">")[1]
		return True

class Word:
	def __init__(self,line="",maxgloss=3,maxsample=10,user=False,language="",text=""):
		self.line=line
		self.maxsample=maxsample
		self.language=language
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
		self.inflections=set([self.mainform])
		self.tally=0 # number of occurrences in reference corpus
		self.successes=[] # number of successful learnings in current pass
		self.failures=[]
		self.history=[] # all learning events in chronological order
		self.notes=[]
		self.sequestered=False
		self.status=1 #available
		self.consolidations=0
		if line:
			lineparts=re.findall("(.*?) \[(.*?)\] \/\((.*?)\) (.+)",line.strip())
			if lineparts: lineparts=lineparts[0]
			if not lineparts: 
				if "[" not in line:
					self.mainform=line.split("/")[0].strip()
					self.phonetic=self.mainform
				else:
					self.mainform=line.split("[")[0].strip()
					self.phonetic=line.split("[")[1].split("]")[0]
					if "(" in self.phonetic or u"£¨" in self.phonetic:
						self.phonetic=self.mainform
				try: 
					self.pos=line.split("(")[1].split(")")[0]
				except IndexError:
					self.pos=""
				if self.mainform.startswith("~"):
					self.pos="suffix"
					self.mainform=self.mainform[1:]
				elif self.mainform.endswith("~"):
					self.pos="prefix"
					self.mainform=self.mainform[:-1]
				if "/" in line:
					self.glossed=line.split("/",1)[1]
			else: 
				self.mainform=lineparts[0].strip()
				phoneticform=lineparts[1].strip()
				if u"(" in phoneticform or u"£¨" in phoneticform or not phoneticform:
					self.phonetic=self.mainform
				else:
					self.phonetic=phoneticform
				self.pos=lineparts[2].strip()
				self.glossed=lineparts[3].replace("(P)","")
			self.rom=self.romanize()	
			self.glossed=re.sub("\(.*?\)"," ",self.glossed).strip()
			self.glosses=[x.strip() for x in self.glossed.split("/") if x][:maxgloss]
			if self.glosses:
				gloss=self.glosses[0]
			else:
				self.gloss=""
		elif text:
			if type(text) != unicode: text=text.decode("utf-8","ignore")
			self.mainform=text.strip()
		if not self.phonetic:
			self.phonetic=self.phonetize()
		if not self.rom:
			self.rom=self.romanize()
		
	def __str__(self):
		if type(self.rom)==unicode:
			return self.rom.encode("utf-8","ignore")
		else:
			return self.rom
		
	def count(self):
		return len([x for x in self.successes if x[2]==-1]) # reverse successes only
	
	def romanize(self): # to override
		return self.phonetic
		
	def phonetize(self):
		return self.mainform

	def succeed(self,sessionid=0,is_practice=False,direction=1,vocab=False,session=False):
		if not vocab: 
			print "Error: no Vocabulary supplied!!!"
			vocab=Vocabulary()
		if session==False:
			session=vocab.session
		timestamp=int(time.time())
		thenumber=(1+int(is_practice)*9)*(1+int(direction==-1))
		print thenumber # 1 for simple forward success, 2 for reverse success; 10,20 if practice
		if direction == 1: # succeeded forward, now to reverse
			session.forward_successes.add(str(self))
			session.todo[-1].add(self)
			try:
				session.todo[1].remove(self)
			except KeyError:
				print "Hey! %s was not in todo[1]" % str(self)
			print "Len todo[1], todo[-1]: ",str(len(session.todo[1])),str(len(session.todo[-1]))
		elif direction == -1:
			session.reverse_successes.add(str(self))
			try:
				session.todo[-1].remove(self)
			except KeyError:
				print "Hey!!! %s was not in todo[-1]" % str(self)
			print "Len todo[-1]: ",str(len(session.todo[1]))
		if not is_practice:
			self.successes.append((timestamp,sessionid,direction))
			self.history.append((thenumber,timestamp,sessionid))
		return thenumber

	def fail(self,sessionid=0,is_practice=False,direction=1,vocab=False,session=False):
		if not vocab: 
			print "Error: no Vocabulary supplied!"
			vocab=Vocabulary()
		if session==False:
			session=vocab.session
		timestamp=int(time.time())
		thenumber=0
		if direction == 1: # succeeded forward, now to reverse
			session.forward_failures.add(str(self))
			try:
				session.todo[1].remove(self)
			except KeyError:
				print "Hey!! %s was not in todo[1]" % str(self)

		elif direction == -1:
			thenumber=-2
			session.reverse_failures.add(str(self))
			try:
				session.todo[-1].remove(self)
			except KeyError:
				print "Hey!!!! %s was not in todo[-1]" % str(self)
		if not is_practice:
			self.failures.append((timestamp,sessionid,direction))
			self.history.append((thenumber,timestamp,sessionid))
			self.successes=[] # restart the clock...
		if session.is_oldcheck:
			self.status==1
			vocab.add(self)
			vocab.session.todo[1].add(self)

	def skip(self,vocab,session=False,direction=1):
		if not session:
			session=vocab.session
		timestamp=int(time.time())
		self.history.append((-1,timestamp,session.id))
		session.todo[direction].remove(self)
	
	def inflect(self):
		if not self.pos.startswith("adj") and not self.pos.startswith("v"): 
			return False
		queryurl="http://en.wiktionary.org/wiki/"+urllib.quote(self.mainform.encode("utf-8"))
		txdata=""
		txheaders={'User-agent' : 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
		req=urllib2.Request(queryurl,txdata,txheaders)
		querypage=urllib2.urlopen(req).read()
		newforms=re.findall('lang\=\"ja\-Jpan\"\>(.+?)\<\/td\>',querypage)
		if not newforms:
			newforms=[x.split("</td>")[0] for x in querypage.split("<td>")[1:] if "</td>" in x]
		try: 
			newforms=[x.split(">")[1].split("<")[0] for x in newforms]
			newforms=[x.decode("utf-8","ignore") for x in newforms]
			newforms=[x.strip() for x in newforms if x.strip()]
			newforms=[x for x in newforms if not re.search("[a-zA-Z]",x)]
		except: 
			return False
		print len(newforms),self.rom
		self.inflections=list(self.inflections)
		self.inflections.extend(newforms)
		self.inflections=set(self.inflections)

	def addsample(self,sample,words,href=""):
		if type(sample) == str or type(sample) == unicode:
			sample=Example(sample,href=href)
		self.tally+=1
		if not self.keyed:
			for x in self.examples:
				simpledom=simplicity(str(x),words)
				if self.mainform in x.text:
					simpledom=simpledom*1.1 # experimental 10% bonus for exact form
				self.keyed.append((simpledom,x))
		if re.search("[a-zA-Z]",str(sample)): 
			return False
		testsample=str(sample).replace(" ","")[:-1] # remove terminal punct.
		if testsample in " ".join([str(x).replace(" ","")[:-1] for x in self.examples]): 
			return False
		if len(testsample)/len(self.mainform) < 2 and len(self.mainform) < 4: 
			return False
		elif len(testsample)-len(self.mainform) < 3: 
			return False
		elif len(testsample.replace(self.mainform,"")) < 3: 
			return False
		simpledom=simplicity(str(sample),words)
		if self.mainform in sample.text:
			simpledom=simpledom*1.1
		self.keyed.append((simpledom,sample))
		self.keyed=list(set(self.keyed)) 
		self.keyed.sort()
		self.keyed.reverse()
		self.keyed=self.keyed[:self.maxsample]
		self.examples=[x[1] for x in self.keyed]
		return True

# dump to pseudo-XML
	def dump(self,all=False,indented="\t",singleindent="\t",encoding="utf-8"): #pseudo-XML fragment
		outstring=indented+'<Word name="%s" status="%s" user="%s" tally="%s">\n' % (self.mainform.encode(encoding,"ignore"),str(self.status),str(self.user),str(self.tally))
		outstring+=indented+singleindent+'<Romanization>%s</Romanization>\n' % self.rom.encode(encoding,"ignore")
		outstring+=indented+singleindent+'<Phonetic>%s</Phonetic>\n' % self.phonetic.encode(encoding,"ignore")
		outstring+=indented+singleindent+'<Gloss>%s</Gloss>\n' % self.gloss.encode(encoding,"ignore")
		outstring+=indented+singleindent+'<Glossed>%s</Glossed>\n' % self.glossed.encode(encoding,"ignore")
		outstring+=indented+singleindent+'<Sequestered>%s</Sequestered>\n' % str(self.sequestered)
		if self.line:
			outstring+=indented+singleindent+'<Line>%s</Line>' % self.line.encode(encoding,"ignore")
		outstring+=indented+singleindent+'<Examples>\n'
		for e in self.examples:
			outstring+=indented+singleindent+singleindent+'<Example href="%s">%s</Example>\n' % (e.href,e.encode(encoding))
		outstring+=indented+singleindent+'</Examples>\n'
		outstring+=indented+singleindent+'<History>\n'
		for h in self.history:
			outstring+=indented+singleindent+singleindent+'<Event value="%s" session="%s">%s</Event>\n' % (str(h[0]),str(h[2]),str(h[1]))
		outstring+=indented+singleindent+'</History>\n'
		outstring+=indented+singleindent+'<Successes>\n'
		for s in self.successes:
			outstring+=indented+singleindent+singleindent+'<Event value="1" direction="%s" session="%s">%s</Event>\n' % (str(s[2]),str(s[1]),str(s[0]))
		outstring+=indented+singleindent+'</Successes>\n'
		outstring+=indented+singleindent+'<Notes>\n'
		for s in self.notes:
			outstring+=indented+singleindent+singleindent+'<Note type="%s" session="%s">%s</Note>\n' % (str(s[1]),str(s[2]),str(s[0]))
		outstring+=indented+singleindent+'</Notes>\n'
		outstring+=indented+singleindent+'<Inflections>\n'
		for i in self.inflections:
			outstring+=indented+singleindent+singleindent+'<Form>%s</Form>\n' % i.encode(encoding,"ignore")
		outstring+=indented+singleindent+'</Inflections>\n'
		outstring+=indented+"</Word>"
		return outstring
		
	def getstars(self):
		outstring=""
		for s in self.successes:
			if s[2] < 0: #reverse success
				outstring+=u"\u2605"
			else:
				outstring+=u"\u2606"
		return outstring
	
	def addnote(self,text="",session=time.time(),type=""):
		self.notes.append((type,session,user,text))

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
		self.sessionid=int(time.time())
		status=(0,0,0)
		self.current_word=Word()
		self.current_text=""
		self.done=set()
		self.can_assess=True
		self.direction=1
		
	def load(self):
		pass

class Group(MetaVocab):
	def __init__(self,maxsize=0,members=set(),tooclose=0.3,language="",filepath="",newwords=[],user=User(""),restorefrom=""):
		MetaVocab.__init__(self,language=language,filepath=filepath,newwords=newwords,user=user,restorefrom=restorefrom)
		self.allwords|=members
		self.words.extend(list(members))
		self.romanizations=set([x.rom for x in self.words])
		self.glosses=set()
		self.wordcloud=set()
		self.max=maxsize
		self.tooclose=tooclose # minimum edit distance between members as divided by word length
		self.storage=set()
		
	def glom(self,argument=[]):
		if not argument:
			argument=[x.mainform for x in self.words]
		glomstring=" ".join(list(argument))
		return glomstring
	
	def ok2add(self,word,definition="",proceed=False,biglist=[],maxoverlap=1,worry_about_length=True):
		if self.max and len(self.words) >= self.max and worry_about_length:
			print "too much",str(self.max),str(len(self.words))
			return False
		if not definition:
			definition=word.glossed
		stringword=word.mainform
		romword=word.rom
		if stringword in self.glom(): #in case there is already a longer word/phrase containing this
			print "mainform in glom"
			return False
		if romword in self.glom(self.romanizations):
			print "rom in glom"
			return False
		closes=[y for y in [(x,romword,2.0*distance(x,romword)/len(romword+x)) for x in self.romanizations] if y[2] < self.tooclose]
		if closes:
			print "close matches", romword,str(closes)
			return False
		elif definition and maxoverlap:
			if definition in self.glom(self.glosses):
				print "def in glom"
				return False
			else:
				cloud=wordcloud(definition)
				if len(cloud.intersection(self.wordcloud)) >= maxoverlap:
					print "max overlap"
					return False
		return True

	def add(self,word,definition="",tupled=False):
		self.words.append(word)
		random.shuffle(self.words)
		self.allwords.add(word)
		self.glosses.add(definition)
		self.wordcloud|=wordcloud(definition)
		if tupled:
			self.storage.add(tupled)
		
class Vocabulary(MetaVocab):
	def __init__(self,language="",newwords=[],user=User(""),restorefrom="",is_practice=False,startnewsession=False,filter=True):
		MetaVocab.__init__(self,language=language,newwords=newwords,user=user,restorefrom=restorefrom)
		words=set(newwords)
		self.words=list(words)
		self.wordsforward=list(words)
		self.wordsreverse=[]
		self.is_practice=is_practice
		self.language=language
		self.user=user
		self.goal=1000
		self.allwords=set(self.words)
		self.sessionid=0
		self.path=""
		self.words_saved=False # to be used only when necessary to temporarily displace wordslist
		if restorefrom:
			self.load(open(restorefrom).read())
			self.path=restorefrom
		if startnewsession:
			self.newsession(0)
		newsess=False
		if not hasattr(self,"session"):
			self.session=Session(self)
			newsess=True
		if filter and newsess: # don't filter if session is in progress.
			status=str(self.filter(thecap=self.user.cycle))
			print "Vocab start status:",status
		else:
			self.words=[x for x in self.allwords if x.status==1]
		try:
			self.current_word=self.words[0]
		except IndexError:
			self.current_word=Word()
		self.session.todo[1]=set(self.words)
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
		self.direction=1
		if output=="gui":
			app=wx.App(False)
			form=ManagerWindow(vocab=self)
			form.Show()
			app.MainLoop()
			del(app)
		elif output=="web": # to do
			pass
	
	def intake(self,input=[]): # for processing a list of new word objects
		#may need to do some additional validation here
		self.filter(input=input,maxnew=self.user.perdiem)
		return (len(input[:self.user.perdiem]),len(self))
	
	def filter(self,thecap=-1,maxnew=0,maxgroup=0,input=[],reviewgap=600000): 
# wherein the words to be actively reviewed in the current session are separated
		review=0
		new=0
		if thecap == -1: # default: use user values
			thecap=self.user.cycle # number of consecutive successes needed
		if not maxgroup:
			maxgroup=int(self.user.perdiem*self.user.cycle*1.5) # allow some accumulation, but not a completely insane amount
			if maxnew+len(self.words) >= maxgroup:
				maxgroup=maxnew+len(self.words)
		self.words=[]  #reset pool of available words
		available=[(len(x.successes)*x.tally,x) for x in self.allwords if x.status==1]
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
			if w.count() >= thecap: # all done?
				w.status=-1 
				self.consolidations+=1
				self.session.consolidated.add(w)
				continue
			if thegroup.ok2add(w):
				thegroup.add(w)
				self.add(w)
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
					print "Sequestered",str(w.sequestered),w.rom,str(seqs[-1][1])
					if time.time()-seqs[-1][1] < reviewgap: # has the allotted time elapsed?
						continue
				elif w.status == 0: #inactive
					dels=[x for x in w.history if x[0]==-100]
					if dels: # has been deleted
						print "deleted",w.rom
						continue
					elif new >= maxnew: 
							print "too many",w.rom
							continue
				if thegroup.ok2add(w): # if we're still here, time to see if this one fits.
					if w.status == 0 and not w.sequestered: 
						new+=1
					else: 
						review+=1
					thegroup.add(w)
					self.activate(w)
				else:
					print "not OK 2 add, ",w.rom
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

	def dump(self,encoding="utf-8"):
		outstring='<Vocabulary language="%s" goal="%s" lastsession="%s">\n' % (str(self.language),str(self.goal),str(self.sessionid))
		outstring+=self.user.dump(indented="\t")
		try:
			outstring+=self.session.dump(indented="\t")
		except AttributeError: # still have session=False?
			outstring+=Session(self).dump(indented="\t")
		for w in self.allwords:
			outstring+=w.dump(encoding=encoding)
		outstring+="</Vocabulary>\n"
		return outstring

	def save(self,filepath=""):
		if not filepath:
			filepath=self.path
		outfile=open(filepath,"w")
		with outfile:
			outfile.write(self.dump())
		return True
		
	def load(self,instring="",encoding="utf-8",status=-1,wordclass=Word): 
		if not instring:
			instring=open(self.path).read()
		print "Input string length: "+str(len(instring))
# load core data
		firstline=instring.split("\n",1)[0]
		if '<Vocabulary' in firstline:
			if 'language="' in firstline:
				self.language=firstline.split('language="',1)[1].split('"')[0]
			if 'goal="' in firstline:
				self.goal=int(firstline.split('goal="',1)[1].split('"')[0])
			if 'lastsession="' in firstline:
				self.sessionid=int(float(firstline.split('lastsession="',1)[1].split('"')[0]))
# load user
		self.user=User()
		try:
			userdata="<User"+instring.split("<User",1)[1].split("</User>")[0]+"</User>"
			self.user.load(userdata)
		except IndexError:
			print "No user data!"
			pass
# load session
		self.session=Session(self)
		try:
			sessiondata="<Session"+instring.split("<Session",1)[1].split("</Session>",1)[0]+"</Session>"
		except IndexError:
			print "No session data!"
			sessiondata=""
			pass
# load words
		wordies=[x.split("</Word")[0].decode(encoding,"ignore") for x in instring.split('<Word name="')[1:]]
		print "#Wordies: ",str(len(wordies))
		for w in wordies:
			text=w.split('"',1)[0]
			word=wordclass(text=text)
			try:
				if status == -1:
					word.status=int(w.split('status="')[1].split('"')[0])
				else:
					word.status=status
			except IndexError:
				pass
			try:
				word.tally=int(w.split('tally="')[1].split('"')[0])
			except IndexError:
				word.tally=0
			word.rom=w.split("<Romanization>")[1].split("</Romanization>")[0]
			word.phonetic=w.split("<Phonetic>")[1].split("</Phonetic>")[0]
			word.gloss=w.split("<Gloss>")[1].split("</Gloss>")[0]
			word.glossed=w.split("<Glossed>")[1].split("</Glossed>")[0]
			history=w.split("<History>")[1].split("</History>")[0]
			hist_events=[x.split("</Event>")[0] for x in history.split("<Event")[1:]]
			for h in hist_events:
				if not h.strip(): continue
				value=int(h.split('value="')[1].split('"',1)[0])
				session=int(float(h.split('session="')[1].split('"',1)[0]))
				timestamp=int(float(h.split(">")[1].split("<")[0]))
				word.history.append((value,timestamp,session))
			success=w.split("<Successes>")[1].split("</Successes>")[0]
			ss=[x.split("</Event>")[0] for x in success.split("<Event")[1:]] 
			for s in ss: # looping through word's successes
				if not s.strip(): continue
				try:
					session=float(s.split('session="')[1].split('"',1)[0])
				except:
					print "Error:::"+s
				try:
					direction=int(s.split('direction="')[1].split('"',1)[0])
				except:
					direction=1
				timestamp=float(s.split(">")[1].split("<")[0])
				word.successes.append((timestamp,session,direction))
			failure=w.split("<History>")[1].split("</History>")[0]
			ff=[x.split("</Event>")[0] for x in failure.split("<Event")[1:]]
			for f in ff:
				if not f.strip(): continue
				session=float(f.split('session="')[1].split('"',1)[0])
				timestamp=float(f.split(">")[1].split("<")[0])
				word.failures.append((timestamp,session))
			try:
				examples=[x.split("</Example>")[0].split(">",1) for x in [y for y in w.split("<Example")[1:] if not y.startswith("s")]]
				examples=[x for x in examples if x[1].strip()]
				for e in examples:
					newexample=Example(e[1].strip())
					if 'href="' in e[0]:
						newexample.href=e[0].split('href="')[1].split('"')[0].encode("utf-8","ignore") # no reason for URL to be in Unicode
					if 'priority="' in e[0]:
						newexample.priority=int(e[0].split('priority="')[1].split('"')[0])
					word.examples.append(newexample)
			except IndexError: print "No examples: ",word.rom
			try:
				seq=w.split("<Sequestered>")[1].split("</Sequestered>")[0]
				if seq.strip().lower() in ["true","false"]:
					word.sequestered=bool(eval(seq.title()))
			except IndexError:
				pass
			self.allwords.add(word)
# finish loading session
		quickfind=dict([(str(x),x) for x in self.allwords])
		self.session.load(sessiondata,quickfind)
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
		word.history.append((100,self.sessionid,time.time()))
		word.successes=[] #reset the counter
		word.sequestered=True
		word.status=newstatus
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
		word.history.append((-100,self.sessionid,time.time()))
		word.sequestered=True
		word.status=0
		if word in self.words:
			print "deleting..."
			self.words.remove(word)
		if hasattr(word,"wordbox"): # replace with blankness?
			self.wordboxes[word].wordbox.SetLabel("")
			self.wordboxes[word].wordbox.SetStyle(wx.DEFAULT)
			self.wordboxes[word].glossbox.SetLabel("")
			self.wordboxes[word].longglossbox.SetLabel("")
			self.wordboxes[word].checkbox.SetValue(False)
			del(self.wordboxes[word])
		return True
	
	def getstats(self):
		doneish=[x for x in self.allwords if len([y for y in x.successes if y[2]==-1])>=self.user.cycle]
		for d in doneish:
			self.sequester(d,newstatus=-1)
		incoming=[x for x in self.words if len(x.successes) == 0]
		seqs=[x for x in self.allwords if x.sequestered] # check use of sequestered bit
		deleteds=[x for x in self.allwords if x.status ==0 and "-100," in str(x.history)]
		self.done=set([x for x in self.allwords if x.status == -1])
		self.activecount=len([x for x in self.allwords if x.status==1])
		known=set()
		known|=set([x for x in self.allwords if x.status == 1 and x.successes])
		known|=set([x for x in self.allwords if x.status == -1 and x.successes])
		self.knowncount=len(known)
		self.session.update_stats()
		if not self.session.forward_total: # i.e. only if count is still at its default value of 0
			self.session.forward_total=self.activecount
		if len(self.words)>self.activecount: # this *shouldn't* be necessary
			self.activecount=len(self.words)
		if not self.session.reverse_total:
			self.session.reverse_total=len(self.session.todo[-1])
		self.sequesteredcount=len(seqs)
		self.deletedcount=len(deleteds)
		self.donecount=len(self.done)
		self.incomingcount=len(incoming)
		self.learningcount=self.activecount+self.donecount
		return (self.activecount,self.learningcount)
	
	def add(self,word):
			self.allwords.add(word)
			self.words.append(word)
			return True
			
	def activate(self,word):
		self.words.append(word)
		word.status=1
		return True
	
	def newsession(self,daysworth=-1,restart=True):
		print "creating new session",str(self.sessionid),str(int(time.time()))
		self.sessionid=int(time.time())
		try:
			self.session=Session(self,self.sessionid)
		except NameError: # error on import
			pass
			print "Unable to create session."
			return False
		if daysworth==-1: #default to user pref
			daysworth=self.user.perdiem
		if self.allwords:
			print "len allwords: "+str(len(self.allwords))
			self.filter(maxnew=daysworth)
			print "new len words: "+str(len(self.words))
		else:
			print "Allwords not found: "+str(len(self.allwords))
		if restart:
			self.session.todo[1]=set(self.words)
		foo=self.getstats()
		print "Done creating session.",str(foo)
		return True
			
	def reset(self): # destroy all data
		self.words=[]
		for a in self.allwords:
			a.status=0
		print len(self.allwords)
		self.newsession(0)
		self.save()
	
class Session:  #information on one learning day; should generally be attached to a Vocabulary
	def __init__(self,vocabulary,id=time.time(),is_practice=False,justnew=False,is_oldcheck=False):
		if not is_practice:
			is_practice=vocabulary.is_practice
		self.is_practice=is_practice
		self.is_oldcheck=is_oldcheck
		self.id=int(id)
		self.language=vocabulary.language
		self.user=vocabulary.user
		if justnew:
			self.cap=self.user.cycle*int(not self.is_practice) # if practice session, only 0s
		else:
			self.cap=self.user.cycle
		self.vocabulary=vocabulary
		try:
			self.vocabulary.current_word=self.vocabulary.words[0]
		except IndexError:
			pass
		self.forward_successes=set()
		self.reverse_successes=set()
		self.forward_failures=set()
		self.reverse_failures=set()
		self.practiced=set()
		self.consolidated=set()
		self.todo={}
		self.todo[1]=set() # dynamic set of words awaiting forward review
		self.todo[-1]=set() # dynamic set of words that have passed forward review and await reversal
		self.redo=set() # set of (direction,word) tuples
		try:
			self.forward_total=self.vocabulary.activecount # static count of total words for forward review
		except AttributeError:
			self.forward_total=0
		self.reverse_total=0
		self.redoing=False
	
	def __len__(self): # primary purpose: return 0/False if no action yet
		return len(self.forward_successes|self.reverse_successes|self.forward_failures|self.reverse_failures)
	
	def update_stats(self): # to be called by Vocabulary.getstats()
		if not self.todo[1] and not self.forward_total: # forward_total check to avoid triggering when set has been emptied
			self.todo[1]=set(self.vocabulary.words)
			self.forward_total=self.vocabulary.activecount
# clear out any sludge that has crept in
		self.todo[1]-=self.forward_successes
		self.todo[-1]-=self.reverse_successes
		print "Updating Session stats: ",str(len(self.todo[1])),str(self.forward_total)
		

	def dump(self,indented=""):
		outstring=indented+'<Session id="%s" user="%s" language="%s">\r\n' % (str(self.id),str(self.user),str(self.language))
		outstring+=indented+'\t<Successes direction="+1" count="%s">\r\n' % str(len(self.forward_successes))

		for s in self.forward_successes:
			outstring+=indented+'\t\t<Success direction="+1">%s</Success>\r\n' % str(s)
		outstring+=indented+"\t</Successes>\r\n"
		outstring+=indented+'\t<Successes direction="-1" count="%s">\r\n' % str(len(self.reverse_successes))	
		for s in self.reverse_successes:
			outstring+=indented+'\t\t<Success direction="-1">%s</Success>\r\n' % str(s)
		outstring+=indented+"\t</Successes>\r\n"
		
		outstring+=indented+'\t<Failures direction="+1" count="%s">\r\n' % str(len(self.forward_failures))
		for s in self.forward_failures:
			outstring+=indented+'\t\t<Failure direction="+1">%s</Failure>\r\n' % str(s)
		outstring+=indented+"\t</Failures>\r\n"
		
		outstring+=indented+'\t<Failures direction="-1" count="%s">\r\n' % str(len(self.reverse_failures))
		for s in self.reverse_failures:
			outstring+=indented+'\t\t<Failure direction="-1">%s</Failure>\r\n' % str(s)
		outstring+=indented+"\t</Failures>\r\n"
		
		outstring+=indented+'\t<Todo direction="+1" total="%s">\r\n' % str(self.forward_total)
		for t in self.todo[1]:
			outstring+=indented+'\t\t<Wordup>%s</Wordup>\r\n' % str(t)
		outstring+=indented+'\t</Todo>\r\n'
		outstring+=indented+'\t<Todo direction="-1" total="%s">\r\n' % str(self.reverse_total)
		for t in self.todo[-1]:
			outstring+=indented+'\t\t<Wordup>%s</Wordup>\r\n' % str(t)
		outstring+=indented+'\t</Todo>\r\n'		
		outstring+=indented+"</Session>\r\n"
		return outstring
		
	def load(self,instring="",quickfind={}):
		instring=instring.strip()
		try:
			topstring=instring.split("<Session ",1)[1].split(">",1)[0]
		except IndexError:
			return False
		self.id=int(topstring.split('id="',1)[1].split('"',1)[0])
		self.user=topstring.split('user="',1)[1].split('"',1)[0]
		self.language=topstring.split('language="',1)[1].split('"',1)[0]
		successforward=instring.split('<Successes direction="+1"',1)[1].split("</Successes>",1)[0]
		self.forward_success=int(successforward.split('count="',1)[1].split('"',1)[0])
		successreverse=instring.split('<Successes direction="-1"',1)[1].split("</Successes>",1)[0]
		self.reverse_success=int(successreverse.split('count="',1)[1].split('"',1)[0])
		failureforward=instring.split('<Failures direction="+1"',1)[1].split("</Failures>",1)[0]
		self.forward_failure=int(failureforward.split('count="',1)[1].split('"',1)[0])
		failurereverse=instring.split('<Failures direction="-1"',1)[1].split("</Failures>",1)[0]
		self.reverse_failure=int(failurereverse.split('count="',1)[1].split('"',1)[0])
		for s in successforward.split("\r\n"):
			if '<Success direction="+1">' not in s: continue
			word=s.split(">",1)[1].split("<",1)[0]
			self.forward_successes.add(word)
		for s in successreverse.split("\r\n"):
			if '<Success direction="-1">' not in s: continue
			word=s.split(">",1)[1].split("<",1)[0]
			self.reverse_successes.add(word)
		for f in failureforward.split("\r\n"):
			if '<Failure direction="+1">' not in s: continue
			word=s.split(">",1)[1].split("<",1)[0]
			self.forward_failures.add(word)
		for s in failurereverse.split("\r\n"):
			if '<Failure direction="-1">' not in s: continue
			word=s.split(">",1)[1].split("<",1)[0]
			self.reverse_failures.add(word)
		todoforward=instring.split('<Todo direction="+1"',1)[1].split("</Todo>",1)[0]
		todoreverse=instring.split('<Todo direction="-1"',1)[1].split("</Todo>",1)[0]
		print "Todo forward, reverse string lengths: ",str(len(todoforward)),str(len(todoreverse))
		try:
			self.forward_total=int(todoforward.split('total="',1)[1].split('"',1)[0])
			self.reverse_total=int(todoreverse.split('total="',1)[1].split('"',1)[0])
		except IndexError:
			pass
		todoes={1:todoforward,-1:todoreverse}
		for t in todoes.keys():
			for s in todoes[t].split("\r\n"):
				if '<Wordup' not in s: continue
				wordform=s.split(">",1)[1].split("<",1)[0].strip()
				try:
					word=quickfind[wordform]
					self.todo[t].add(word)
					word.status=1
				except KeyError:
					print "Error! %s not in vocabulary." % wordform
		return True
		

# data gathering

class Source:
	def __init__(self,title="Misc",langcode="EN",subject="news",date=datetime.date.today()):
		self.title=title
		self.langcode=langcode
		self.subject=subject
		self.starturl=""
		self.maindirectory=os.path.join("D:\\Corp",title)
		try:
			os.mkdir(self.maindirectory)
		except:
			pass
		self.datestring=date.isoformat().replace("-","")
		self.directory=os.path.join(self.maindirectory,self.datestring)
		try:
			os.mkdir(self.directory)
		except:
			pass
		try:
			self.already=os.listdir(self.directory)
		except:
			self.directory=self.directory.replace("D:\\Corp","/home/calumet/%s/%s/%s" % (langcode,subject,title))
			try: os.mkdir(self.directory)
			except: pass
			self.already=os.listdir(self.directory)
		self.pattern="(?i)\<a\s+href=\"(.*?)\""
		self.headers={'User-agent' : 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
		self.source=False
		self.date=datetime.date.today()
		self.postdata=""
		self.baseurl=""
		self.loginurl=False
		self.cachefirst=False
		self.usefirstname=False
		self.firstmore=False
		self.firstmore_increment=1
		self.firstmore_start=1
		self.firstmore_pattern="%s/%s"
		self.firstpattern=False
		self.secondaries=False
		self.tertiaries=False
		self.done=set()
		self.todo=set()
		self.repeatsok=False
		self.updateonly=True
		self.throwouts=[]
		self.throwout_unless=""
		self.suffix=".html"

	def grabhandle(self,url):
		if re.match("http[s]*\:/\/",url):
			if self.postdata:
				req=urllib2.Request(url,self.postdata,self.headers)
			else:
				req=url
			print "Downloading "+url
			try: handle=urllib2.urlopen(req,timeout=10)
			except: return False
			return handle.read()
		else:
			print "Invalid: "+url
			return False

	def cycle(self):
		fornext=self.firstdown()
		count=1
		while count < self.limit:
			try: fornext=self.downbatch(fornext)
			except TypeError: break
			count+=1
			
	def process_page(self,text=""):
		if not self.pattern: #to download all matches of pattern on page
			self.pattern="http\:\/\/[\S]+?"
		firsturls=set()
		if self.firstpattern: patterns=[self.pattern,self.firstpattern]
		else: patterns=[self.pattern]
		for pattern in patterns:
			found=set(re.findall(pattern,text))
			print len(text),pattern,len(found)
			for p in found:
				if self.throwout_unless:
					if not re.search(self.throwout_unless,p): 
						continue
				if self.throwouts:
					throwout=False
					for t in self.throwouts:
						if t and re.search(t,p): 
							throwout=True
							break
					if throwout: continue
				firsturls.add(p)
		print len(firsturls)
		firsturls=set([self.fixurl(x) for x in firsturls])
		self.todo|=firsturls
		return firsturls

	def fixurl(self,input=""): # for overriding
		return input

	def go(self):
		self.firstdown()
		self.downbatch(self.todo)
	
	def getmore(self):
		count=self.firstmore_start
		stillmore=1
		while stillmore:
			time.sleep(1)
			url=self.firstmore_pattern % (self.starturl,str(count*self.firstmore_increment))
			try: 
				page=urllib2.urlopen(url,timeout=10)
			except:
				time.sleep(5)
				continue
			if not page:
				continue
			count+=1
			stillmore=len(self.process_page())

	def firstdown(self):
		text=self.grabhandle(self.starturl)
		if not text: return False
		if not self.usefirstname:
			firstname="firstfile.html"
		else:
			firstname=self.starturl.split("/")[-1]
		self.process_page(text)
		if self.firstmore:
			text+=self.getmore()
		writefile=open(os.path.join(self.directory,"firstfile.html"),"w")
		with writefile:
			writefile.write(text)

	def downbatch(self,urls=set()):
		for f in urls-self.done:
			if f in self.done: continue
			filename=self.filefromurl(f)
			if filename in self.already: 
				if self.updateonly:
					continue
				elif self.repeatsok:
					count=1
					filename=filename+"_"+str(count)+self.suffix
					while filename in alreadythere:
						count+=1
						filename=filename.split("_")[0]+"_"+str(count)+self.suffix
			text=self.grabhandle(f)
			if not text:
				text=self.grabhandle(f)
				if not text: 
					print "unable to download "+f
					continue
			print filename
			writefile=open(os.path.join(self.directory,filename),"w")
			with writefile:
				writefile.write("<url>"+f+"</url>")
				writefile.write(text)
			if not self.repeatsok: self.done.add(f.split("#")[0])

	def filefromurl(url):
		return f.split("/")[-1].split("?")[0].split("#")[0][:100]+self.suffix

# -- interface objects -- #

class HtmlWin(HtmlWindow):
	def __init__(self, parent):
		wx.html.HtmlWindow.__init__(self,parent, wx.ID_ANY)
		if "gtk2" in wx.PlatformInfo:
			self.SetStandardFonts()

	def OnLinkClicked(self, link):
		wx.LaunchDefaultBrowser(link.GetHref())

class CardForm(wx.Frame):  # flashcard test interface
	def __init__(self,parent,vocab,username="",language="",direction=1,session=0,dothese=[],is_practice=False,is_oldcheck=False):
# initial viability check
		self.dead=False
		print "Creating cardform"
		if session==0:
			self.session=vocab.session
		else:
			self.session=session
		if not (self.session.todo[1]|self.session.todo[-1]) and not dothese:
			print "Dead session: "+str(len(self.session.todo[1])),str(len(self.session.todo[-1])),str(len(vocab.words))
			self.dead=True
			return # dies a-borning
		elif not dothese:
			dothese=self.session.todo[direction]
			if not dothese:
				print "Undead session.",str(direction)
				return
# basic setup
		self.dothese=list(dothese)
		self.dothese_saved=False
		self.is_practice=is_practice
		self.is_oldcheck=is_oldcheck
		random.shuffle(self.dothese)
		self.sessiondirection=direction
		self.direction=direction # 1 = forward, -1=back -- current direction of card
		self.parent=parent
		self.vocab=vocab
		self.vocab.current_word=self.dothese[0]
		if not language:
			language=parent.vocab.language
		if not username:
			username=str(parent.vocab.user)
		self.statusfile=vocab.path

#foundations for display		
		titlestring="Flashcards for %s, learning %s" % (username,language)		
		if self.is_practice:
				titlestring+=" (Practice Session)"
		wx.Frame.__init__(self, parent, wx.ID_ANY, titlestring,size=wx.Size(600,600))
		self.SetIcon(self.parent.icon)
		self.shown=0 # start with details hidden
		self.nulldict=dict([(x,"") for x in self.dothese]) # useful nullity
		if hasattr(self.dothese[0],"mainform"):
			self.examples=dict([(x,x.phonetic) for x in self.dothese]) # will display phonetic form on request, just below main form
			self.examples2={}
			for v in self.dothese:
				self.examples2[v]="\n".join(u'<P>%s <A href="%s">\u2197</A></P>\n<P></P>' % (x.text,x.href.decode("utf-8","ignore")) for x in v.examples)
		else:
			self.examples=self.nulldict
			self.examples2=self.nulldict
		if self.sessiondirection == 1:
			self.current_text=self.vocab.current_word.mainform
		elif self.sessiondirection == -1:
			self.current_text=self.vocab.current_word.gloss

# actual display formatting
		self.panel = wx.Panel(self, wx.ID_ANY)
		self.wordfont=wx.Font(35,wx.DEFAULT,wx.NORMAL,wx.NORMAL)
		self.wordfont_small=wx.Font(20,wx.DEFAULT,wx.NORMAL,wx.NORMAL)
		examplefont=wx.Font(15,wx.DEFAULT,wx.NORMAL,wx.NORMAL)
		littlefont=wx.Font(8,wx.DEFAULT,wx.NORMAL,wx.NORMAL)
		color = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE)
		self.color=color
		self.atext = wx.TextCtrl(self.panel, value=self.current_text,style=wx.EXPAND|wx.TE_READONLY|wx.ALIGN_CENTER|wx.BORDER_NONE|wx.TE_MULTILINE|wx.TE_NO_VSCROLL,size=wx.Size(300,75))
		self.atext.SetLabel(self.current_text)
		self.atext.SetBackgroundColour(self.color)
		self.atext.SetFont(self.wordfont)
		self.btext = wx.TextCtrl(self.panel, value="",style=wx.EXPAND|wx.TE_READONLY|wx.ALIGN_CENTER|wx.TE_MULTILINE|wx.BORDER_NONE|wx.TE_NO_VSCROLL,size=wx.Size(300,50))
		self.btext.SetLabel("")
		self.btext.SetFont(examplefont)
		self.btext.SetBackgroundColour(self.color)

#space for example sentences
#		self.ctext = wx.html.HtmlWindow(self.panel, value="",style=wx.EXPAND|wx.TE_READONLY|wx.BORDER_NONE|wx.TE_NO_VSCROLL|wx.TE_MULTILINE,size=wx.Size(300,250))
		self.ctext = HtmlWin(self.panel)
		cstring=u'<?xml version="1.0" encoding="utf-8"?> <HTML>\n<BODY>\n%s</BODY>\n</HTML>' % self.examples2[self.vocab.current_word]
		if self.vocab.language=="Korean":
			self.ctext.SetFonts("Gulim","Gulim") # necessary for rendering
		try:
			cstring=cstring.encode("utf-8","ignore")
		except UnicodeDecodeError:
			pass
		self.ctext.SetPage(cstring)
		self.ctext.SetBackgroundColour(self.color)
		self.ctext.SetSize(wx.Size(300,250))
		self.ctext.Show()

# space for history info
		dstring=self.vocab.current_word.getstars()
		if dstring:
			dstring+=u"\r\n"
		dstring+=self.vocab.current_word.show_history()
		self.dtext = wx.TextCtrl(self.panel, value="",style=wx.EXPAND|wx.TE_READONLY|wx.BORDER_NONE|wx.TE_NO_VSCROLL|wx.TE_MULTILINE,size=wx.Size(300,250))
		self.dtext.SetLabel(dstring)
		self.dtext.SetBackgroundColour(color)
		self.dtext.SetFont(littlefont)
		self.dtext.HideNativeCaret()

# display of current-session info
		self.countstring="Word %s of %s, direction: %s" 
		self.update_count()
		self.counttext=wx.StaticText(self.panel, label=self.countstring2)
		self.counttext.SetFont(littlefont)

# sizer setup
		sizer = wx.BoxSizer(wx.VERTICAL)
		hsizer=wx.BoxSizer(wx.HORIZONTAL)
		row1=wx.BoxSizer(wx.HORIZONTAL)
		row2=wx.BoxSizer(wx.HORIZONTAL)
		row3=wx.BoxSizer(wx.HORIZONTAL)
		column=wx.BoxSizer(wx.VERTICAL)
		column.Add(self.counttext,0)
		column.Add(self.dtext,0)
		sizer.Add(self.atext,0)
		sizer.Add(self.btext,0)

#button setup
		self.ybutton = wx.Button(self.panel, id=wx.ID_ANY, label="&Yes", name="yes")
		self.nbutton = wx.Button(self.panel, id=wx.ID_ANY, label="&No", name="no")
		self.gotbutton=wx.Button(self.panel, id=wx.ID_ANY , label="&Rock solid", name="Done")
		self.sbutton = wx.Button(self.panel, id=wx.ID_ANY, label="&Skip -- try later", name="skip")
		self.qbutton = wx.Button(self.panel, id=wx.ID_ANY, label="&End this session, save results", name="quit")
		if self.is_practice:
			self.qbutton.SetLabel("&End this session")
		self.obutton = wx.Button(self.panel, id=wx.ID_ANY, label="&Go back", name="oops")
		self.obutton.Disable() # until first update()
		self.fbutton = wx.Button(self.panel, id=wx.ID_ANY, label="&Flip card", name="flip")
		self.dbutton = wx.Button(self.panel, id=wx.ID_ANY, label="Show/hide &details", name="details")
		self.rbutton = wx.Button(self.panel, id=wx.ID_ANY, label="Too &confusing (remove for now)", name="remove")
		
		self.ybutton.SetToolTip(wx.ToolTip("I know it."))
		self.nbutton.SetToolTip(wx.ToolTip("I don't know it."))
		self.dbutton.SetToolTip(wx.ToolTip("Show the examples and phonetic form."))
		ftext={1:"English definition",-1:"%s word" % self.vocab.language}
		self.fbutton.SetToolTip(wx.ToolTip("Show the %s." % ftext[self.direction]))
		self.qbutton.SetToolTip(wx.ToolTip("Close cleanly."))
		self.sbutton.SetToolTip(wx.ToolTip("Go to next card, and come back later."))
		self.obutton.SetToolTip(wx.ToolTip("Undo your last action and go back to previous card."))
		self.rbutton.SetToolTip(wx.ToolTip("Get rid of this for now, learn it later."))
		self.gotbutton.SetToolTip(wx.ToolTip("I am 100% confident that I know and will not forget this word."))

		self.wordbuttons=[self.ybutton,self.nbutton,self.gotbutton,self.sbutton,self.fbutton,self.dbutton,self.rbutton]
		buttons1 = [self.ybutton, self.nbutton]
		buttons2 = [self.dbutton,self.fbutton]
		buttons3=  [self.qbutton]
		buttons4= [self.sbutton,self.obutton,self.rbutton,self.gotbutton]

		for button in buttons1:
			self.buildButtons(button, row1)
		for button in buttons2:
			self.buildButtons(button,row2)
		for button in buttons3:
			self.buildButtons(button,row3)
		for button in buttons4:
			self.buildButtons(button,column)
		
#		sizer.Add(self.bouncer)
		sizer.Add(row1)
		sizer.Add(row2)
		sizer.Add(self.ctext,0)
		sizer.Add(row3)
		hsizer.Add(sizer)
		hsizer.Add(column)
		self.panel.SetSizer(hsizer)
		self.panel.SetAutoLayout(True)
#		hsizer.Fit(self.panel)
		self.hsizer=hsizer
		self.panel.Refresh()
		self.dbutton.SetFocus()
		self.Bind(wx.EVT_CLOSE, self.OnClose)
	
	def update_count(self):
		directions={1:"forward",-1:"reverse"}
		direction=directions[self.sessiondirection]
		if self.session.redoing:
				direction+=" (redo)"
		self.countstring2=self.countstring % (str(self.dothese.index(self.vocab.current_word)+1),str(len(self.dothese)),direction)

	def buildButtons(self, btn, sizer):
		btn.Bind(wx.EVT_BUTTON, self.onButton)
		sizer.Add(btn, 0, wx.ALL, 5)

	def onButton(self, event):
		button = event.GetEventObject()
		response=button.GetName()[:1]
		if response == "y":
			self.vocab.current_word.succeed(self.session.id,self.is_practice,self.sessiondirection,vocab=self.vocab,session=self.session)
		elif response == "n":
			self.vocab.current_word.fail(self.session.id,self.is_practice,self.sessiondirection,vocab=self.vocab,session=self.session)
			if self.is_practice:
				self.session.redo.add((self.sessiondirection,self.vocab.current_word)) # for practice session, repeat until done
			if self.is_oldcheck:
				self.parent.wordboxes[self.vocab.current_word]=False
		elif response == "s":#skip
			self.vocab.current_word.skip(session=self.session,vocab=self.vocab,direction=self.sessiondirection)
			self.session.redo.add((self.sessiondirection,self.vocab.current_word))
		elif response == "o": # oops  
			if not self.is_practice:
				foo=self.vocab.undo(session=self.session,direction=self.sessiondirection)
			self.session.todo[self.sessiondirection].add(self.vocab.current_word)
			index=self.dothese.index(self.vocab.current_word)
			self.vocab.current_word=self.dothese[index-1]
			print index
			self.update()
			return #don't advance
		elif response == "q": # quit and save
			if not self.is_practice:
				self.closeout()
			else:
				self.OnClose()
			return
		elif response == "f": #flip
			self.flip()
			self.nbutton.SetFocus()
			self.sbutton.Disable()
			return
		elif response == "d": #details toggle
			self.showhide()
			self.nbutton.SetFocus()
			return
		elif response == "r": #remove
			index=self.dothese.index(self.vocab.current_word)
			self.parent.vocab.sequester(self.vocab.current_word)
			self.dothese.remove(self.vocab.current_word)
			if index==len(self.dothese): index-=1
			try:
				self.vocab.current_word=self.dothese[index]
				self.direction=self.sessiondirection
				self.update()
				return
			except:
				print "Exception R!"
				self.onend()
				return
		elif response == "D": #done with 
			print "Removing rock-solid word."
			self.vocab.current_word.succeed(self.session.id,vocab=self.vocab,session=self.session)
			self.vocab.current_word.history.append((400,time.time(),self.session.id))
			self.vocab.sequester(self.vocab.current_word,newstatus=-1)
			try:
				self.vocab.current_word=self.vocab[index]
				self.direction=self.sessiondirection
				self.update()
				return
			except:
				print "Exception D!"
				self.onend()
				return
			return
		self.ybutton.Disable()
		self.nbutton.Disable()
		time.sleep(0.5)
		outcome=self.advance()
		self.direction=self.sessiondirection
		if outcome != False: # avoid double update
			self.update()
		
	def OnClose(self,event=False):
		if event:
			print "triggered close event."
			if not self.is_practice and not self.is_oldcheck:
				dia = wx.MessageDialog(self, "If you exit now, all of your activity for this session will be lost.  Click \"End this session, save results\" to save your work.", "Confirm Exit", wx.OK|wx.CANCEL|wx.ICON_QUESTION)
				if dia.ShowModal() == wx.ID_OK:
#					self.vocab.newsession(0,restart=False)
					pass
				else:
					dia.Destroy()
					return
		else: # "quit and save"
			print "Saving on close..."
			self.vocab.save()
		if self.is_practice:
			self.parent.vocab.session.practiced|=self.forward_successes
			print "len practiced: ",str(len(self.parent.vocab.session.practiced)),str(len(self.vocab.words))
		print "setting gauges on close"
		self.parent.setGauges()
		self.final_tidy()
		self.parent.refresh()
		self.Destroy()
	
	def final_tidy(self):
		if self.session.redoing: #done with current redo, put things back in order
			self.session.redoing=False
			print "restoring words saved : ",str(len(self.vocab.words)),str(len(self.vocab.words_saved))
			self.vocab.words=self.vocab.words_saved
			self.dothese=self.dothese_saved
			self.vocab.words_saved=False
			self.dothese_saved=False
		if self.is_practice:
			self.vocab.current_word=self.vocab.words[0] #reset the ticker
	
	def advance(self):
		print "Advancing..."
		try: # proceed to next card
			self.vocab.current_word=self.dothese[self.dothese.index(self.vocab.current_word)+1]
			print self.dothese.index(self.vocab.current_word)
		except IndexError:
			print "Reached end."
			self.onend()
			return False
		if self.sessiondirection == 1:
			self.current_text=self.vocab.current_word.mainform
		elif self.sessiondirection == -1:
			self.current_text=self.vocab.current_word.gloss

	def update(self,is_end=False): #update displays for new word
# restore defaults
		print "updating."
		self.atext.SetFont(self.wordfont)
		if is_end:
			self.current_text="the end."
			print self.current_text
			self.shown=False
		elif self.sessiondirection == 1:
			self.current_text=self.vocab.current_word.mainform
		elif self.sessiondirection == -1:
			self.current_text=self.vocab.current_word.gloss
		if len(self.current_text) > 10:
			print "reducing font..."
			self.atext.SetFont(self.wordfont_small)
		self.atext.SetLabel(self.current_text)
		print "Updating card, #successes: "+self.vocab.current_word.rom,len(self.vocab.current_word.successes)
		dstring=self.vocab.current_word.getstars()
		dstring+=u"\r\n"
		dstring+=self.vocab.current_word.show_history()
		self.dtext.SetLabel(dstring)
		cstring=u'<HTML>\n<BODY>\n%s</BODY>\n</HTML>' % self.examples2[self.vocab.current_word]
		try:
			cstring=cstring.encode("utf-8","ignore")
		except UnicodeDecodeError:
			pass
		self.ctext.SetPage(cstring)
		self.ctext.Show(self.shown)
		if self.shown:
			if self.sessiondirection == 1:
				self.btext.SetLabel(self.examples[self.vocab.current_word])
			else:
				self.btext.SetLabel(self.vocab.current_word.glossed)
				self.btext.SetLabel(self.vocab.current_word.glossed)
		else:
			self.btext.SetLabel("")
		self.update_count()
		self.counttext.SetLabel(self.countstring2)
		self.obutton.Enable(bool(self.dothese.index(self.vocab.current_word)>0))
		for b in self.wordbuttons: b.Enable(bool(not is_end))

	def onend(self):
		if self.session.redoing: #done with current redo, put things back in order
			print "restoring words saved : ",str(len(self.dothese)),str(len(self.dothese_saved))
			self.vocab.words=self.vocab.words_saved
			self.dothese=self.dothese_saved
			self.dothese_saved=False
			self.vocab.words_saved=False
			self.session.redoing=False
			self.vocab.current_word=self.dothese[-1] # restore to previous position at end of list
		if self.session.redo:
			if not self.vocab.words_saved: # avoid overwrite by multiple redoes
				self.vocab.words_saved=list(self.vocab.words)
				self.dothese_saved=list(self.dothese)
			print "Redo: "+str(len(self.vocab.words))
# now put things in order 
			self.session.todo[self.sessiondirection]=set(x[1] for x in self.session.redo)
			self.dothese=[x[1] for x in self.session.redo]
			print self.sessiondirection,len(self.session.todo[self.sessiondirection])
			self.session.redo=set()
			self.session.redoing=True
			if self.sessiondirection==-1:
				self.reverse_total=len(self.session.todo[-1])
			self.vocab.current_word=self.dothese[0]
		elif self.is_practice and self.sessiondirection==1: # reverse course ... currently allow this for practice slices only; require two full button-presses for real thing.
			print "Reversing..."
			self.sessiondirection=-1
			self.direction=-1
			random.shuffle(self.dothese)
			self.vocab.current_word=self.dothese[0]
			self.current_text=self.dothese[0].gloss
			self.update()
		else:
			print "is end."
			self.update(is_end=True)

	def closeout(self):
			dump=self.vocab.dump()
			self.parent.refresh()
			if self.statusfile:
				file=open(self.statusfile,"w")
				with file:
					file.write(dump)
			self.OnClose()

	def flip(self):
		self.atext.SetFont(self.wordfont)
		if self.direction==-1:
			if len(self.vocab.current_word.mainform) > 10:
				print "reducing font."
				self.atext.SetFont(self.wordfont_small)
		elif self.direction==1:
			if len(self.vocab.current_word.gloss) > 10:
				print "reducing font.."
				self.atext.SetFont(self.wordfont_small)			
		if self.sessiondirection == 1:
			if self.direction==1:
				self.atext.SetLabel(self.vocab.current_word.gloss)
				self.ctext.Hide()
				if self.shown:
					self.btext.SetLabel(self.vocab.current_word.glossed) #long-form defn
				else:
					self.btext.SetLabel("")
			elif self.direction==-1:
				self.atext.SetLabel(self.vocab.current_word.mainform)
				if self.shown:
					self.btext.SetLabel(self.examples[self.vocab.current_word]) #long-form defn
					self.ctext.Show()
				else:
					self.btext.SetLabel("")
					self.ctext.Hide()
		elif self.sessiondirection == -1:
			if self.direction==1:
				self.atext.SetLabel(self.vocab.current_word.gloss)
				if self.shown:
					self.btext.SetLabel(self.vocab.current_word.glossed) #long-form defn
				else:
					self.btext.SetLabel("")
			elif self.direction==-1:
				self.atext.SetLabel(self.vocab.current_word.mainform)
				if self.shown:
					self.btext.SetLabel(self.examples[self.vocab.current_word]) #long-form defn
					self.ctext.Show()
				else:
					self.btext.SetLabel("")
					self.ctext.Hide()
		self.direction=0-self.direction

	def showhide(self):
			print "Shown, direction: "+str(self.shown),str(self.direction)
			self.shown=list(set([0,1])-set([self.shown]))[0]
			if self.shown==0:
				self.btext.SetLabel("")
				self.ctext.Hide()
			elif self.direction==1:
				self.btext.SetLabel(self.examples[self.vocab.current_word])
				self.ctext.Show()
			elif self.direction==-1:
				self.btext.SetLabel(self.vocab.current_word.glossed)
				self.ctext.Hide()
			print self.shown

class LevelTest:
	def __init__(self):
		self.done=set()
		self.wordlist=[]
		self.bandwidth=500
		self.chunksize=50
		
	def go(self,thelist=[]):
		if not thelist:
			thelist=self.wordlist
			if not thelist:
				return False
		prepped=self.prepleveltest(thelist)
		result=self.dynamic_ez(prepped)
		resultupled=[(x,result[x]) for x in result.keys()] # avoid annoyances of randomosity
		resultupled.sort()
		return resultupled 
	
	def prepleveltest(bigwordlist=[]): # must be sorted list of strings or word objects or (freq,string) tuples, from most to least frequent
		bands=[]
		self.wordlist=list(bigwordlist)
		while bigwordlist:
			bands.append(set(bigwordlist[:self.bandwidth]))
			bigwordlist=bigwordlist[self.bandwidth:]
		output=[(self.bandwidth*bands.index(x),random.sample(x,self.chunksize)) for x in bands]
		return output
		
	def leveltest_ez(input=[(0,set())]):
		pass
		
	def leveltest_mc(input=[(0,set())]):
		pass

	def dynamic_ez(input=[(0,[""])]):
		app=wx.App(False)
		outcome={}
		previous=False
		for b in input:
			banded=bandtest_ez(b[1])
			if type(banded) == tuple and banded[0] == False:
				print "Cancelled"
				return outcome
			outcome[b[0]]=10.0*banded
			print b[0],outcome[b[0]]
			if previous:
				loopcheck=0
				while outcome[previous[0]] - outcome[b[0]] < -15.0: # going backwards? should normally be positive, but allowing down to -15 to avoid excess looping
					loopcheck+=1
					if loopcheck > 3: break
					try:
						newprev=10*bandtest_ez(previous[1])
						outcome[previous[0]]=0.5*(outcome[previous[0]]+newprev)
						newthis=10*bandtest_ez(b[1])
						outcome[b[0]]=0.5*(outcome[b[0]]+newthis)
					except TypeError: #cancelled
						print "Cancelled"
						return outcome
			if outcome[b[0]] < 25.0: # are we past the point of diminishing returns?
				break
			previous=b
		return outcome
		
	def bandtest_ez(wordset):
		if type(list(wordset)[0]) == tuple:
			wordset=set([x[1] for x in list(wordset)])
		wordset=[str(x) for x in wordset]
		thelist=list(wordset)
		random.shuffle(thelist)
		chunks=[]
		thescore=0.0*10
		yes=0
		c=thelist[:5]
		for word in c:
			card=wx.MessageDialog(None, str(word), "Do you know this word?",wx.YES_NO |wx.CANCEL|wx.NO_DEFAULT )
			response=card.ShowModal()
			if response == wx.ID_YES:
				yes+=1
			elif response == wx.ID_CANCEL:
				return (False,thescore)
			card.Destroy()
		newscore=10.0*yes/5
		return newscore

class ManagerWindow(wx.Frame):
	def __init__(self,vocab,direction=1,loadsource=""):
		print "Creating manager window"
		language=vocab.language
		wx.Frame.__init__(self, None, wx.ID_ANY, "LanguagePie Vocabulary Manager for %s, learning %s" % (str(vocab.user),vocab.language),size=wx.Size(600,500))
		self.tabs=wx.Notebook(self, -1,wx.Point(0,0), wx.Size(0,0), style=wx.NB_FIXEDWIDTH|wx.NB_RIGHT)
		iconpath=os.path.join(workingdir,"picon2.ico")
		self.icon = wx.Icon(iconpath, wx.BITMAP_TYPE_ICO)
		self.SetIcon(self.icon)
		self.vocab=vocab
		self.color = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE)
		self.language=vocab.language
		self.direction=direction
		self.loadsource=loadsource
		self.currentdir=os.getcwd()
		self.wordboxes=dict([(x,False) for x in self.vocab.words])
		self.panel = wx.Panel(self.tabs, wx.ID_ANY)
		self.panel2 = wx.Panel(self.tabs, wx.ID_ANY)
		self.panel3=wx.lib.scrolledpanel.ScrolledPanel(self.tabs, wx.ID_ANY, style=wx.TAB_TRAVERSAL)
		self.panel4 = wx.Panel(self.tabs, wx.ID_ANY)
#		self.panel5 = wx.Panel(self.tabs, wx.ID_ANY)
#		self.panel6= wx.Panel(self.tabs, wx.ID_ANY)

		self.tabs.AddPage(self.panel,"Main")
		self.tabs.AddPage(self.panel2,"Pie")
		self.tabs.AddPage(self.panel3,"Edit")
		self.tabs.AddPage(self.panel4,"Settings")
#		self.tabs.AddPage(self.panel5,"Texts")
#		self.tabs.AddPage(self.panel6,"Testing")
		self.labelstring="You are currently in the process of learning %s words of %s. You have an estimated %s vocabulary, including words in all stages of learning, of %s words. " 
		self.labelstring+="\r\nYour current learning day began %s hours ago."
		self.atext = wx.TextCtrl(self.panel, value=self.labelstring % (str(self.vocab.activecount),self.language,self.language,str(self.vocab.activecount+self.vocab.donecount),str(round((time.time()-self.vocab.sessionid)/3600,1))),style=wx.EXPAND|wx.TE_READONLY|wx.BORDER_NONE|wx.TE_MULTILINE|wx.TE_NO_VSCROLL,size=wx.Size(300,80))
		self.atext.SetBackgroundColour(self.color)
		self.practicestring0="2. Practice: %s words available."
		self.practicetext0=wx.StaticText(self.panel, label=self.practicestring0 % len(set(self.vocab.words)-set(self.vocab.session.practiced)))
		self.practicetext1=wx.StaticText(self.panel, label="Review a slice of ")
		self.practicetext2=wx.StaticText(self.panel, label=" words")
		self.practiceinput=wx.TextCtrl(self.panel, value=str(self.vocab.user.chunksize),size=wx.Size(20,20))
		if len(self.vocab.words) < self.vocab.user.chunksize:
			self.practiceinput.SetValue(str(len(self.vocab.words)))
		self.practicegauge=wx.Gauge(self.panel, wx.ID_ANY, 100, size=(20, 100),style=wx.GA_VERTICAL)
		self.practicebutton3=wx.Button(self.panel, id=wx.ID_ANY, label="&Take a bite", name="3-Practice")
		self.practicebutton3.Bind(wx.EVT_BUTTON,self.onButton)
		self.practicebutton3.SetToolTip(wx.ToolTip('Review up to %s words' % self.vocab.user.chunksize))
		self.pracresetbutton=wx.Button(self.panel,id=wx.ID_ANY, label="&Reset",name="Reset")
		self.pracresetbutton.Bind(wx.EVT_BUTTON,self.onButton)
		self.pracresetbutton.SetToolTip(wx.ToolTip('Start practice again from the beginning.'))
		self.newwordstring="&New words only (%s)"
		self.pracbox=wx.CheckBox(self.panel,0, self.newwordstring % str(len([x for x in self.vocab.words if len(x.successes)==0 and x not in self.vocab.session.practiced])))
		self.pracbox.Bind(wx.EVT_CHECKBOX,self.setGauges)

#Defining sizers for manager window
		
		mainsizer=wx.BoxSizer(wx.VERTICAL)
		pracsizer=wx.BoxSizer(wx.HORIZONTAL)
		pracsizer2=wx.BoxSizer(wx.HORIZONTAL)
		pracbutsizer=wx.BoxSizer(wx.VERTICAL)
		newdaysizer=wx.BoxSizer(wx.HORIZONTAL)
		if self.vocab.donecount:
			oldsizer=wx.BoxSizer(wx.HORIZONTAL)
		else: 
			oldsizer=False
		line1sizer=wx.BoxSizer(wx.HORIZONTAL)
		colsizer=wx.BoxSizer(wx.HORIZONTAL)
		column1=wx.BoxSizer(wx.VERTICAL)
		column2=wx.BoxSizer(wx.VERTICAL)

# Daytest control & monitoring
		self.stage1string="Cards for forward review today: %s\r\nCards done: %s"
		self.stage2string="Cards ready for reverse review today: %s\r\nCards done: %s"
		self.stage1 = wx.StaticText(self.panel, label=self.stage1string % (str(len(self.vocab.words)),str(len(self.vocab.session.forward_successes)+len(self.vocab.session.forward_failures))))
		self.stage2 = wx.StaticText(self.panel, label=self.stage2string % (str(self.vocab.session.reverse_total),str(len(self.vocab.session.reverse_successes)+len(self.vocab.session.reverse_failures))))
		self.gobutton=wx.Button(self.panel, id=wx.ID_ANY, label="&Go", name="1-start")
		self.gobutton.Bind(wx.EVT_BUTTON, self.onButton)
		self.gobutton.SetToolTip(wx.ToolTip('Review all active cards from %s to English' % self.vocab.language))
		self.gobutton2=wx.Button(self.panel, id=wx.ID_ANY, label="&Go", name="2-start")
		self.gobutton2.Bind(wx.EVT_BUTTON, self.onButton)
		self.gobutton2.SetToolTip(wx.ToolTip('Review all successfully-reviewed cards, this time from English to %s' % self.vocab.language))
		self.beforegobutton=wx.StaticText(self.panel, label="3. ")

		self.newdaystring1="1. Start new day, loading "
		self.newdaystring2=" new or inactive words: "
		self.newdaytext1=wx.StaticText(self.panel,label=self.newdaystring1)
		self.newdaytext2=wx.StaticText(self.panel,label=self.newdaystring2)
		self.newdayinput=wx.TextCtrl(self.panel, value=str(self.vocab.user.perdiem),size=wx.Size(50,20))
		self.newdaybutton=wx.Button(self.panel, id=wx.ID_ANY, label="&New day", name="newday")
		self.newdaybutton.Bind(wx.EVT_BUTTON, self.onButton)
		self.newdaybutton.SetToolTip(wx.ToolTip('Load up to %s words from the current vocabulary file.' % self.newdayinput.GetValue()))

		if oldsizer:
			self.oldstring1="1a. Check your memory of up to "
			self.oldstring2=" words you have already learned: "
			self.oldtext1=wx.StaticText(self.panel,label=self.oldstring1)
			self.oldtext2=wx.StaticText(self.panel,label=self.oldstring2)
			self.oldinput=wx.TextCtrl(self.panel, value=str(self.vocab.user.perdiem),size=wx.Size(50,20))
			if self.vocab.donecount < self.vocab.user.perdiem:
				self.oldinput.SetValue(str(self.vocab.donecount))
			self.oldbutton=wx.Button(self.panel, id=wx.ID_ANY, label="&Do it now", name="oldcheck")
			self.oldbutton.Bind(wx.EVT_BUTTON, self.onButton)
			self.oldbutton.SetToolTip(wx.ToolTip('Review up to %s words you finished at least %s days ago.' % (self.oldinput.GetValue(),str(self.vocab.user.cycle))))
		else:
			oldsizer=False

		self.gauger1=wx.Gauge(self.panel, wx.ID_ANY, 100, size=(200, 20))
		self.gauger2=wx.Gauge(self.panel, wx.ID_ANY, 100, size=(200, 20))
		foo=self.setGauges()
		bar=self.setButtons()

		line1sizer.Add(self.atext)

		newdaysizer.Add(self.newdaytext1)
		newdaysizer.Add(self.newdayinput)
		newdaysizer.Add(self.newdaytext2)
		newdaysizer.Add((15,15),1)
		newdaysizer.Add(self.newdaybutton)
		
		if oldsizer:
			oldsizer.Add(self.oldtext1)
			oldsizer.Add(self.oldinput)
			oldsizer.Add(self.oldtext2)
			oldsizer.Add((15,15),1)
			oldsizer.Add(self.oldbutton)

		pracsizer.Add(self.practicetext1,0)
		pracsizer.Add(self.practiceinput,0)
		pracsizer.Add(self.practicetext2,0)
		pracbutsizer.Add(self.practicebutton3,0)
		pracbutsizer.Add(self.pracresetbutton,0,wx.ALIGN_BOTTOM)
		pracsizer2.Add(pracbutsizer)
		pracsizer2.Add(self.practicegauge,0)

		column1.Add(self.practicetext0)
		column1.Add(pracsizer)
		column1.Add(pracsizer2,0,wx.ALIGN_BOTTOM)
		column1.Add(self.pracbox)
		
		column2.Add(self.beforegobutton)
		column2.Add(self.stage1,0)
		column2.Add(self.gobutton,0)
		column2.Add((15,15),1)
		column2.Add(self.gauger1,0)
		column2.Add((15,15),1)
		column2.Add(self.stage2,0)
		column2.Add((15,15),1)
		column2.Add(self.gobutton2,0)
		column2.Add((15,15),1)
		column2.Add(self.gauger2,0)
		
		colsizer.Add(column1)
		spaceout=wx.TextCtrl(self.panel, style=wx.EXPAND|wx.TE_READONLY|wx.ALIGN_CENTER|wx.BORDER_NONE|wx.TE_MULTILINE|wx.TE_NO_VSCROLL,size=wx.Size(100,100))
		spaceout.SetBackgroundColour(self.color)
		colsizer.Add(spaceout)
		colsizer.Add(column2)
		mainsizer.Add(line1sizer)
		mainsizer.Add((15,15),1)
		mainsizer.Add(newdaysizer)
		mainsizer.Add((15,15),1)
		if oldsizer:
			mainsizer.Add(oldsizer)
			mainsizer.Add((15,15),1)
		mainsizer.Add(colsizer)

		self.panel.SetSizer(mainsizer)
		self.panel.SetAutoLayout(True)

		if not self.vocab:
			try:
				self.loadFile(find_statusfile(self.currentdir))
			except:
				pass
			
		self.buildEditor()
		self.buildSettings()
		self.drawPie()
		self.Refresh()
		self.panel.Refresh()

	def saveandclose(self,event):
		try:
			self.vocab.save()
		except:
			print "Unable to save."
		self.Destroy()
		
	def setButtons(self):
		self.gobutton.Enable(bool(self.vocab.session.todo[1]))
		self.gobutton2.Enable(bool(self.vocab.session.todo[-1]))
		self.practicebutton3.Enable(bool(self.vocab.activecount > len(self.vocab.session.practiced) and self.vocab.activecount))

	def setGauges(self,event=False): #event is thrown away
		val1=100.0*(float(len(self.vocab.session.forward_successes)+len(self.vocab.session.forward_failures)))/float(self.vocab.activecount+int(self.vocab.activecount==0))
		val2=100.0*(float(len(self.vocab.session.reverse_successes)+len(self.vocab.session.reverse_failures))/(float(len(self.vocab.session.forward_successes)+int(len(self.vocab.session.forward_successes)==0))))
		if self.pracbox.GetValue(): # new only
			activenew=len([x for x in self.vocab.words if not x.successes])
			print activenew,len(self.vocab.session.practiced)
			val3=100.0*(float(len([x for x in self.vocab.session.practiced if not x.successes]))/(activenew+int(activenew==0)))
		else:
			val3=100.0*(float(len(self.vocab.session.practiced))/(self.vocab.activecount+int(self.vocab.activecount==0)))
		self.gauger1.SetValue(val1)
		self.gauger2.SetValue(val2)
		self.practicegauge.SetValue(val3)
		print str((val1,val2,val3))
		return (val1,val2,val3)

	def onButton(self,event): # buttons in manager window
		button = event.GetEventObject()
		response=button.GetName()[:1]
		print response
		if response =="1": #start test
			if not self.vocab.session.todo[1]:
				print "Nothing to do!"
			else:
				self.form=CardForm(parent=self,vocab=self.vocab,direction=1,dothese=self.vocab.session.todo[1])
				if self.form and not self.form.dead:
					self.form.Show()
		elif response == "2": # test reverse
			if not self.vocab.session.todo[-1]:
				print "Nothing to do."
			else:
				self.form=CardForm(parent=self,vocab=self.vocab,direction=-1,dothese=self.vocab.session.todo[-1])
				if self.form and not self.form.dead:
					self.form.Show()
		elif response == "3": # practice slice
			chunksize=int(self.practiceinput.GetValue())
			newonly=bool(self.pracbox.GetValue())
			chunk=list(set(self.vocab.words)-self.vocab.session.practiced)
			if newonly:
				chunk=[x for x in chunk if len(x.successes)==0]
			chunk=chunk[:chunksize]
			if chunk:
				print len(chunk)
				practicesession=Session(self.vocab,is_practice=True)
				practicesession.todo[1]=set(chunk)
				self.form=CardForm(parent=self,vocab=self.vocab,session=practicesession,is_practice=True,dothese=chunk)
				if self.form and not self.form.dead:
					self.form.Show()
		elif response == "R": # reset practice counter
			self.vocab.session.practiced=set()
			print "reset..."
			self.refresh()
		elif response=="f": # load new vocab file
			dialog = wx.FileDialog (self.panel, message = 'Open vocabulary file', wildcard = "Text files (*.txt)|*.txt", style = wx.OPEN )
			if dialog.ShowModal() == wx.ID_OK:
				selected = dialog.GetPath()
				self.loadFile(selected)
			dialog.Destroy()
		elif response == "n": # "New day"
			daysworth = self.newdayinput.GetValue() # currently entered #words to get for new day
			try: 
				daysworth=int(daysworth)
				print "Daysworth: "+str(daysworth)
			except: 
				print "Error on daysworth "+str(daysworth)
			self.vocab.newsession(daysworth=daysworth)
			for w in set(self.vocab.words)-set(self.wordboxes.keys()):
				self.addbox(w)
			self.refresh()
			self.vocab.save()
		elif response == "o":
			chunksize=int(self.oldinput.GetValue())
			available=self.vocab.review_old()
			if not available: 
				self.oldbutton.Disable()
			else:
				chunk=available[:chunksize]
				oldsession=Session(self.vocab)
				oldsession.is_oldcheck=True
				self.vocab.current_word=chunk[0]
				self.form=CardForm(parent=self,vocab=self.vocab,session=oldsession,is_oldcheck=True,dothese=chunk)
				if self.form and not self.form.dead:
					self.form.Show()
				if chunksize >= len(available):
					self.oldbutton.Disable()
					self.oldbutton.SetToolTip(wx.ToolTip("Oops -- none available at this time."))
				
		
	def drawPie(self):
		self.piesizer=wx.BoxSizer(wx.VERTICAL)
		togo=self.vocab.goal-self.vocab.donecount-self.vocab.activecount
		self.piepart1="Words to learn: %s" % str(togo)
		self.piepart2="Words learned: %s" % str(self.vocab.donecount)
		self.piepart3 = "Words in progress: %s" % self.vocab.activecount
		self.explode=(0,0.05,0.05)
		self.fracs=[togo,self.vocab.donecount,self.vocab.activecount]		
#		labels=(self.piepart1,self.piepart2,self.piepart3)
		self.pielabels=None
		self.pie=PiePanel(self.panel2,explode=self.explode,fracs=self.fracs,labels=self.pielabels,size=wx.Size(200,200))
		self.pie.SetBackgroundColour(self.color)
		self.piesizer.Add(self.pie)
		self.piesizer.Layout()
		self.panel2.SetSizer(self.piesizer)
		self.panel2.SetAutoLayout(True)
		self.piesizer.Fit(self.panel2)

	def updatePie(self):
		self.fracs=[self.vocab.goal-self.vocab.donecount-self.vocab.activecount,self.vocab.donecount,self.vocab.activecount]
		self.pie.redraw(self.explode,self.fracs,self.pielabels)

	def buildEditor(self):
		panel=self.panel3

		applybutton=wx.Button(panel, id=wx.ID_ANY, label="Apply and &save", name="apply",style=wx.EXPAND)
		saveasbutton=wx.Button(panel, id=wx.ID_ANY, label="Apply and Save &As", name="saveas",style=wx.EXPAND)
		cancelbutton=wx.Button(panel, id=wx.ID_ANY, label="&Cancel changes", name="cancel",style=wx.EXPAND)
		applybutton.Bind(wx.EVT_BUTTON, self.applyChanges)
		cancelbutton.Bind(wx.EVT_BUTTON, self.applyChanges)
		saveasbutton.Bind(wx.EVT_BUTTON, self.applyChanges)
		applybutton.SetToolTip(wx.ToolTip('Save to currently-loaded file.'))
		saveasbutton.SetToolTip(wx.ToolTip('Save to a new file.'))
		cancelbutton.SetToolTip(wx.ToolTip('Cancel everything.'))

		buttonsizer=wx.BoxSizer(wx.HORIZONTAL)
		buttonsizer.Add(applybutton)
		buttonsizer.Add((20,20), 1) 		
		buttonsizer.Add(cancelbutton)
		buttonsizer.Add((20,20), 1)
		buttonsizer.Add(saveasbutton)

		self.editorsizer=wx.BoxSizer(wx.VERTICAL)
		self.editorsizer.Add(buttonsizer)
		self.editorsizer.Add((5,5),1)

		for word in (x for x in self.vocab.words if not self.wordboxes[x]):
			self.addbox(word)
		self.editorsizer.Layout()
		panel.SetSizer(self.editorsizer)
		panel.SetAutoLayout(True)
#		self.editorsizer.Fit(panel)
		panel.SetupScrolling()
		return True
		
	def addbox(self,word):
		panel=self.panel3

		thing=Nullity() # carrier object
		thing.wordsizer=wx.BoxSizer(wx.HORIZONTAL)
		thing.wordsizer2=wx.BoxSizer(wx.HORIZONTAL)
		thing.wordbox=wx.TextCtrl(panel, value=word.mainform,size=wx.Size(150,20),style=wx.TE_READONLY)
		thing.glossbox=wx.TextCtrl(panel, value=word.gloss,size=wx.Size(100,20))
		thing.longglossbox=wx.TextCtrl(panel, value=word.glossed,size=wx.Size(200,20))
		thing.checkbox=wx.CheckBox(panel,0,"Delete")

		thing.wordsizer.Add(thing.wordbox,1)
		thing.wordsizer.Add(thing.glossbox,1)
		thing.wordsizer2.Add(thing.longglossbox)
		thing.wordsizer2.Add(thing.checkbox)

		self.wordboxes[word]=thing

		self.editorsizer.Add(thing.wordsizer)
		self.editorsizer.Add(thing.wordsizer2)
		self.editorsizer.Add((5,5),1)
		self.editorsizer.Layout()

		panel.SetSizer(self.editorsizer)
		panel.SetAutoLayout(True)
		panel.SetupScrolling()

	def applyChanges(self,event): # editor button bindings
		button = event.GetEventObject()
		response=button.GetName()[:1]
		print response,response
		if response == "a" or response == "s":
			for word in [x for x in self.vocab.words if self.wordboxes[x]]:
				if self.wordboxes[word].checkbox.GetValue():
					self.vocab.delete(word)
					print word.rom,"d"
					self.wordboxes[word].checkbox.Hide()
				if self.wordboxes[word].glossbox.GetValue().strip() != word.gloss.strip():
					word.gloss=self.wordboxes[word].glossbox.GetValue().strip()
					print word.rom,word.gloss
				if self.wordboxes[word].longglossbox.GetValue().strip() != word.glossed.strip():
					word.glossed=self.wordboxes[word].longglossbox.GetValue().strip()
					print word.rom,word.glossed
			if response=="a":
				try:
					self.vocab.save()
				except:
					print "Unable to save."
		self.panel3.Refresh()
		self.buildSettings()
		return response
	
	def loadFile(self,selected):
		if hasattr(self,"filer"):
			self.filer.SetLabel("")
			self.filer.AppendText(selected)
		try:
			newwords=Vocabulary(restorefrom=selected)
			if newwords:
				self.filebefore.SetLabel("Loaded vocabulary.")
				del self.vocab
				self.vocab=newwords
				self.vocab.path=selected
				for n in newwords:
					self.addbox(n)
				self.refresh()
			elif hasattr(self,"filer"):
				self.filebefore.SetLabel("Unable to load.")
				self.refresh()
		except:
			if hasattr(self,"filer"):
				self.filelabel="Invalid file."
				self.filebefore.SetLabel(self.filelabel)
				self.refresh()
			
	def saveFile(self):
		directory=os.getcwd()
		dialog = wx.FileDialog (self.panel, message = 'Save vocabulary file', wildcard = "Text files (*.txt)|*.txt", style = wx.SAVE | wx.FD_OVERWRITE_PROMPT | wx.FD_CHANGE_DIR )
		outcome=dialog.ShowModal()
		if outcome == wx.ID_OK:
				selected = dialog.GetPath()
				print selected
				self.vocab.path=selected
				output=self.vocab.dump()
				outfile=open(selected,"w")
				with outfile:
					outfile.write(output)
		dialog.Destroy()			

	def refresh(self):
		self.vocab.getstats()
		print "Refreshing manager window..."
		self.atext.SetLabel(self.labelstring % (str(self.vocab.activecount),self.vocab.language,self.vocab.language,str(self.vocab.activecount+self.vocab.donecount),str(round((time.time()-self.vocab.sessionid)/3600,1))))
		self.stage1.SetLabel(self.stage1string % (str(len(self.vocab.words)),str(len(self.vocab.session.forward_successes)+len(self.vocab.session.forward_failures))))
		self.stage2.SetLabel(self.stage2string % (str(self.vocab.session.reverse_total),str(len(self.vocab.session.reverse_successes)+len(self.vocab.session.reverse_failures))))
		praclabel=self.practicestring0 % len(set(self.vocab.words)-set(self.vocab.session.practiced))
		self.practicetext0.SetLabel(praclabel)
		self.pracbox.SetLabel(self.newwordstring % str(len([x for x in self.vocab.words if len(x.successes)==0 and x not in self.vocab.session.practiced])))
		toprac=set(self.vocab.words)-self.vocab.session.practiced
		if len(toprac) < self.vocab.user.chunksize:
			self.practiceinput.SetValue(str(len(toprac)))
		else:
			self.practiceinput.SetValue(str(self.vocab.user.chunksize))
		foo=self.setGauges()
		print "Gauges set: ",str(foo)
		boxables=set(self.vocab.words)-set(self.wordboxes.keys())
		for word in boxables:
			self.addbox(word)
		self.setButtons()
		self.updatePie()
	
	def buildButtons(self, btn, sizer):
		btn.Bind(wx.EVT_BUTTON, self.onButton)
		sizer.Add(btn, 0, wx.ALL, 5)
		
	def buildSettings(self,isagain=False):
		vsizer=wx.BoxSizer(wx.VERTICAL)
		panel=self.panel4
		applybutton=wx.Button(panel, id=wx.ID_ANY, label="Apply and &save", name="apply",style=wx.EXPAND)
		saveasbutton=wx.Button(panel, id=wx.ID_ANY, label="Apply and Save &As", name="saveas",style=wx.EXPAND)
		cancelbutton=wx.Button(panel, id=wx.ID_ANY, label="&Cancel changes", name="cancel",style=wx.EXPAND)
		self.filelabel="Select a new vocabulary:"
		self.filebefore = wx.StaticText(panel, label=self.filelabel)
		self.filer= wx.TextCtrl(panel, value=self.vocab.path,size=wx.Size(150,30),style=wx.EXPAND)
		filebutton=wx.Button(panel, id=wx.ID_ANY, label="Select &file ", name="file")

		applybutton.Bind(wx.EVT_BUTTON, self.applySettings)
		cancelbutton.Bind(wx.EVT_BUTTON, self.applySettings)
		saveasbutton.Bind(wx.EVT_BUTTON, self.applySettings)
		filebutton.Bind(wx.EVT_BUTTON,self.applySettings)

		buttonsizer=wx.BoxSizer(wx.VERTICAL)
		buttonsizer.Add(applybutton)
		buttonsizer.Add((5,5)) 		
		buttonsizer.Add(cancelbutton)
		buttonsizer.Add((5,5))
		buttonsizer.Add(saveasbutton)
		vsizer.Add(buttonsizer)
		vsizer.Add((5,5))

# setting up the settings
		cyclestring="Number of consecutive days of accurate recall required before a word is considered known: "
		cycletext=wx.StaticText(panel, label=cyclestring)
		self.cyclefield=wx.TextCtrl(panel, value=str(self.vocab.user.cycle),size=wx.Size(150,20))
		perdiemstring="Number of new words to be added per day: "
		perdiemtext=wx.StaticText(panel, label=perdiemstring)
		self.perdiemfield=wx.TextCtrl(panel,value=str(self.vocab.user.perdiem),size=wx.Size(150,20))
		vsizer.Add(cycletext)
		vsizer.Add(self.cyclefield)
		vsizer.Add((5,5))
		vsizer.Add(perdiemtext)
		vsizer.Add(self.perdiemfield)
		vsizer.Add((5,5))
		vsizer.Add(self.filebefore)
		filesizer=wx.BoxSizer(wx.HORIZONTAL)
		filesizer.Add(self.filer)
		filesizer.Add(filebutton)
		vsizer.Add(filesizer)

# final setup		
		vsizer.Layout()
		panel.SetSizer(vsizer)
		panel.SetAutoLayout(True)
		return True

	def applySettings(self,event):
		button = event.GetEventObject()
		response=button.GetName()[:1]
		if response == "a" or response == "s":
			self.vocab.user.perdiem=int(self.perdiemfield.GetValue())
			self.vocab.user.cycle=int(self.cyclefield.GetValue())
			if self.vocab.path and response == "a": # apply & save
				writefile=open(self.vocab.path,"w")
				with writefile:
					writefile.write(self.vocab.dump())
			else: # save as, or no filepath designated
				self.saveFile()
		elif response=="f":
			dialog = wx.FileDialog (self.panel, message = 'Open vocabulary file', wildcard = "Text files (*.txt)|*.txt", style = wx.OPEN )
			if dialog.ShowModal() == wx.ID_OK:
				selected = dialog.GetPath()
				self.loadFile(selected)
			dialog.Destroy()
		elif response=="c":
			self.buildSettings()
		self.buildSettings()

class PiePanel (wx.Panel):
	def __init__( self, parent, color=None, dpi=None, explode=(0, 0.05, 0, 0), fracs=[15,30,45, 10], labels=('Frogs', 'Hogs', 'Dogs', 'Logs'),**kwargs ):
		from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
		from matplotlib.figure import Figure
		if 'id' not in kwargs.keys():
			kwargs['id'] = wx.ID_ANY
		if 'style' not in kwargs.keys():
			kwargs['style'] = wx.NO_FULL_REPAINT_ON_RESIZE
		wx.Panel.__init__( self, parent, **kwargs )
		self.parent=parent
		self.figure = Figure( (4,4), dpi )
		self.canvas = FigureCanvasWxAgg( self, -1, self.figure )
		self.SetColor( color )
		self.ax = self.figure.add_axes([0.1, 0.1, 0.8, 0.8])
		pies=self.ax.pie(fracs, explode=explode, labels=labels, shadow=True)
		self.draw()
		self._resizeflag = False

	def SetColor( self, rgbtuple=None ):
		"""Set figure and canvas colours to be the same."""
		if rgbtuple is None:
			rgbtuple = wx.SystemSettings.GetColour( wx.SYS_COLOUR_BTNFACE ).Get()
		clr = [c/255. for c in rgbtuple]
		self.figure.set_facecolor( clr )
		self.figure.set_edgecolor( clr )
		self.canvas.SetBackgroundColour( wx.Colour( *rgbtuple ) )
	
	def redraw(self,explode=False,fracs=False,labels=False):
#		self.figure.clf(True)
		if explode:
			self.explode=explode
		if fracs:
			self.fracs=fracs
		if labels:
			self.labels=labels
		pies=self.ax.pie(fracs, explode=explode, labels=labels, shadow=True)
		self.draw()

	def draw( self ):
		print "Drawing", str(self.GetSize())
		self.canvas.draw()

# -- End of class definitions -- #

# miscellaneous utility functions

def wordcloud(definition): #generates a cloud of associated words from a definition string
		words=set(re.findall("[a-zA-Z\-]+",definition))-stops
		synsets=[]
		cloud=set()
		return words

# FIXME -- everything below this point is WN-dependent		
		for w in words:
			synsets.extend(wn.synsets(w))
			for synset in synsets:
				output=[]
				lemmata=synset.lemmas
				try: output.append(synset.holonyms())
				except AttributeError: pass
				try: output.extend(synset.hypernyms())
				except AttributeError: pass
				try: output.extend(synset.meronyms())
				except AttributeError: pass
				try: output.extend(synset.troponyms())
				except AttributeError: pass
				try: output.extend(synset.hyponyms())
				except AttributeError: pass
			# now, get synonyms
				output.extend([str(x).split(".")[-1][:-2] for x in lemmata])
				for ell in lemmata:
					output.extend(ell.antonyms())  # don't want antonyms, probably...
					output.extend(ell.derivationally_related_forms())
					output.extend(ell.pertainyms())
				newout=[str(x).replace('_'," ") for x in output if "Synset" not in str(x) and "Lemma" not in str(x)]
				newout.extend([str(x).split(".")[0][8:].replace("_"," ") for x in output if "Synset" in str(x)])
				newout.extend([str(x).split(".")[0][7:].replace("_"," ") for x in output if "Lemma" in str(x)])
				output=newout
				cloud|=set(output)
		return cloud

def sortem(words=[],segment=100,groups=False,maxoverlap=1,tooclose=0.3,definitions=[]): # words may either be a flat wordlist or a dict of definitions
# or a list of tuples with the the first item being a sequence key and the second the word itself
	print len(words)
	if not groups:
		print "Fresh start"
		groups=[Group(segment,tooclose=tooclose)]
	if type(words) == list:
		pass
	else:
		defined=words
		words=words.keys()
	if type(words[0]) != tuple:
		wordlist=[(words.index(x),x) for x in words]
	else:
		wordlist=words
	wordlist.sort()
	print len(wordlist)
	for word in wordlist:
		w=word[1]
		print str(w),str(len(groups))
		needmore=True
		for g in groups:
			neighbors=[]
			index=groups.index(g)
			if index > 0:
				neighbors.append(groups[index-1])
			if index > len(groups)-1:
				neighbors.append(groups[index+1])
			if g.ok2add(w,maxoverlap=maxoverlap):
				if False in [x.ok2add(w,maxoverlap=maxoverlap,worry_about_length=False) for x in neighbors]: 
					continue
				needmore=False
				if defined:
					g.add(w,defined[word],tupled=word)
				else:
					g.add(w,tupled=word)
				break
		if needmore:
			newgroup=Group(segment,set([w]),tooclose=tooclose)
			if defined:
				newgroup.glosses=set([defined[word]])
				newgroup.wordcloud=wordcloud(defined[word])
			newgroup.storage.add(word)
			groups.append(newgroup)
	return groups
		
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

def purge(wordlist):
	newlist=[]
	for w in wordlist:
		if type(w) != unicode: raise TypeError
		w=w.encode("utf-8","ignore").decode("utf-8","ignore").strip()
		problem=[unicodedata.category(x) for x in w if not unicodedata.category(x).startswith("L")]
		if problem:
			print w.encode("cp949","ignore"),str(problem)
		else:
			newlist.append(w)
	return newlist

def sortem(words,size=100,maxoverlap=1,tooclose=0.3): # List of JaWord objects for sorting
	sort_freq=[(x.tally,100.0/(1.0+words.index(x)),x) for x in words] #prioritize -- first by frequency, second by initial ranking
	sort_freq.sort()
	sort_freq.reverse()
	words=[x[2] for x in sort_freq]
	defined=dict([((words.index(x),x.rom),"".join(x.glosses[:1])) for x in words])
	romanized=dict([((words.index(x),x.rom),x) for x in words]) #store info for  de-romanizing after sort
	sorted=indo.sortem2(defined,size,tooclose=tooclose,maxoverlap=maxoverlap)
	for group in sorted:
		group.members=set([romanized[x] for x in group.storage]) #de-romanize
	return sorted

def sortem2(words=[],segment=100,groups=False,maxoverlap=1,tooclose=0.3,definitions=[]): # words may either be a flat wordlist or a dict of definitions
# or a list oftuples withthe the first item being a sequence key and the second the word itself
	print len(words)
	if not groups:
		print "Fresh start"
		groups=[Group(segment,tooclose=tooclose)]
	if type(words) == list:
#		words=set(words)
		pass
	else:
		defined=words
		words=words.keys()
	if type(words[0]) != tuple:
#		wordlist=set([(x,words.index(x)) for x in words])
		wordlist=[(words.index(x),x) for x in words]
	else:
		wordlist=words
	wordlist.sort()
	print len(wordlist)
	for word in wordlist:
		w=word[1]
		print w,str(len(groups))
		needmore=True
		for g in groups:
			neighbors=[]
			index=groups.index(g)
			if index > 0:
				neighbors.append(groups[index-1])
			if index > len(groups)-1:
				neighbors.append(groups[index+1])
			if g.ok2add(w,maxoverlap=maxoverlap):
				if False in [x.ok2add(w,maxoverlap=maxoverlap,worry_about_length=False) for x in neighbors]: 
					continue
				needmore=False
				if defined:
					g.add(w,defined[word],tupled=word)
				else:
					g.add(w,tupled=word)
				break
		if needmore:
			newgroup=Group(segment,set([w]),tooclose=tooclose)
			if defined:
				newgroup.glosses=set([defined[word]])
				newgroup.wordcloud=wordcloud(defined[word])
			newgroup.storage.add(word)
			groups.append(newgroup)
	return groups

def sortemout(groups):
	allthewords=[]
	for g in groups:
		allthewords.extend(g.members)
	return allthewords

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

def clean_text_wiki(text):
		text=re.sub("\{\{[\s\S]+\}\}"," ",text)
		text=re.sub("\[\[.*?\|(.*?)\]\]","\\1",text)
		text=re.sub("\[[\S]+(.*?)\]","\\1",text)
		text=re.sub("\<.*?\>"," ",text)
		text=text.replace("[[","")
		text=text.replace("]]","")
		text=text.strip()
		while text.startswith("*") or text.startswith(":") or text.startswith("#"):
			text=text[1:]
		return text
			
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
			if a in sentence: 
				sentence=sentence.replace(a," ")
		except UnicodeDecodeError:
			print "Exception decoding!"
	sentence=sentence.replace(" ","")
	newlength=len(sentence)
	simplicity=100*(float(oldlength-newlength)/float(oldlength) ** 1.5) # slight penalty for length
	return simplicity

def indexit(words,path=""):
	output=""
	for word in words:
		samples="\t".join(word.examples)
		output+=u"%s\t%s\t%s\t%s\t%s\n" % (word.mainform,word.phonetic,word.rom," / ".join(word.glosses),samples)
	outfile=open(path,"w")
	with outfile:
		try: 
			outfile.write(output.encode("utf-8","ignore"))
		except:
			print "Error!"
	return output
	
def restore(filepath):
	words=[]
	file=open(filepath)
	for line in file:
		line=line.strip()
		if line.count("\t") < 3: continue
		line=line.decode("utf-8","ignore")
		lineparts=line.split("\t")
		word=Word()
		word.mainform=lineparts[0]
		word.phonetic=lineparts[1]
		word.rom=lineparts[2]
		word.glossed=lineparts[3]
		word.glosses=lineparts[3].split(" / ")
		try: 
			word.gloss=word.glosses[0]
			word.gloss=re.sub("\(.*?\)"," ",word.gloss).strip()
		except IndexError:
			word.gloss=""
		word.examples=[Example(x) for x in lineparts[4:]]
		words.append(word)
	return words

def run3(langcode=""):
	import sys
	file=""
	try:
		arg=sys.argv[1].strip()
		if "." not in arg:
			langcode=arg
		else:
			file=arg
	except IndexError:
		pass
	if not file:
		file=find_statusfile(langcode=langcode)
	file=os.path.join(workingdir,file)
	print "Starting up from "+file
	try:
		foo=Vocabulary(restorefrom=file)
	except:
		foo=Vocabulary()
	foo.run()

def find_statusfile(langcode="",directory=workingdir):
	files=os.listdir(directory)
	thefile=""
	statusfiles=[x for x in files if "statusfile" in x]
	if "statusfile.txt" in files:
		thefile="statusfile.txt"
	if statusfiles and not thefile:
		thefile=statusfiles[0]
	if langcode: # not elif
		findthisfile=langcode+"-statusfile.txt"
		if findthisfile in statusfiles:
			thefile=findthisfile
	return thefile

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

	
if __name__ == "__main__" :
	import sys
	outfile=open("latest_log.txt","a")
	sys.stdout=outfile
	sys.stderr=outfile
	print datetime.datetime.today().isoformat()
	run3()