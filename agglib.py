#!/usr/bin/python
# -*- coding: utf-8  -*-

'''

Functions for use in generating lists of words lacking Wiktionary coverage.
Does not include downloaders.  The assumption is that the files are already in place in a dedicated directory on the hard drive. (e.g. "C:\Corpus\Calcutta_Star_2009-01-01")
In addition, it is assumed that the working list of English titles, named "en_titles.txt", is already present in the same directory in which the script lives.

This code is currently quite rough, and is being debugged only very gradually through painful experience.  Use at your own risk.

'''

import datetime
import locale
import os
import re
import time
from copy import copy
import wikipedia
from htmlentitydefs import name2codepoint

try: 
	import lid	
	import MontyTagger, MontyLemmatiser
except ImportError: pass


punctuation="!\"#$%&'()*+,-./:;<=>?@[\]^_`{|}~’”“"
scriptdir="C:\Code" # Where the code and control files live
actiondir="C:\Action" # Where hardlinks are placed for lists that are ready for proofreading.  Currently rigged for Windows only.

locale.setlocale(locale.LC_ALL,"English_US")

class ufo: #Thanks to Robert Ullmann for this bit of simple magic.
	year=datetime.date.today().year
	month=datetime.date.today().month

	def __init__(self, **k):
		for a in k: setattr(self, a, k[a])

	def __str__(self):
		return self.year+"-"+self.month


class sourceobject:
	file=""
	sourcename=""
	sourcey=""
	sourcegroup=""
	convertentities=True
	enforce_paragraphs=False
	encoding="iso-8859-1"
	extracted=False
	pagefromcite=False
	format="html"
	sourcetype="news"
	year=str(datetime.date.today().year)
	date=datetime.date.today().strftime("%B %d").replace(" 0"," ")
	day=""
	authormatchers=[]
	datematchers=[]
	doimatchers=False
	pagematchers=False
	sourcematchers=False
	titlematchers=[]
	urlmatchers=["\<url\>(.*?)\<\/url\>"]
	volmatchers=False
	issuematchers=False
	includers=False
	skipincluders=False
	replacers=False
	author=""
	page=""
	pages=""
	text=""
	title=""
	toctext=""
	url=""
	volume=""
	doi=""
	issue=""
	urlcore=""
	headertemplate=""
	getstring="\<[pP][^\>]*\>([\s\S]*?)\<\/[pP]\>"
	goodtags=["sub","sup","i","em"]
	authorcleaner=False
	datecleaner=""
	titlecleaner=""
	noforeign=False
	def textprep(self): #Cleanup before extraction
		prepped=unicode(self.text,self.encoding,errors="ignore")
		checked=self.verify_encoding(prepped.encode("utf-8"))
		if checked != self.encoding:
#			print "Changing encoding to "+checked
			prepped=unicode(self.text,checked,errors="ignore")
		self.text=prepped
		if self.convertentities:
			self.text=self.text.replace("&nbsp;"," ")
			self.text=unescape(self.text).encode("utf-8")
		else:
			self.text=self.text.encode("utf-8")
		if self.replacers:
			for r in self.replacers:
				self.text=re.sub(r,self.replacers[r],self.text)
	def getdatum(self,matchlist,default=""):
		datum=default
		if matchlist: 
			for m in matchlist:
				if re.search(m,self.text):
					datum=re.search(m,self.text).group(1)
					if datum != "":
						break
		return datum

	def getinfo(self):
		specials={"&agr;":"&#945;","&bgr;":"&#946;","&dgr;":"&#948;"} # Annoying extra entities used by Nature, probably others
		for s in specials.keys():
			self.text=self.text.replace(s,specials[s])
		self.getauthor()
		self.getdate()
		self.getdoi()
		self.getissue()
		self.getpage()
		self.getsource()
		self.gettitle()
		self.geturl()
		self.getvolume()

	def getauthor(self):
		self.author=self.getdatum(self.authormatchers)
		self.authorclean()

	def getdate(self,default=datetime.date.today().isoformat()):
		self.date=self.getdatum(self.datematchers,default)
#		print self.date
		self.dateclean()

	def getdoi(self):
		self.doi=self.getdatum(self.doimatchers)

	def getissue(self):
		if self.issuematchers:
			self.issue=self.getdatum(self.issuematchers)

	def getpage(self):
		if self.pagematchers: 
			self.page=self.getdatum(self.pagematchers)
			if self.sourcegroup=="Science":
				if "-" in self.page:
					endpoints=self.page.split("-")
					endpoints=[e.replace("\t","").replace("\n","") for e in endpoints]
					self.pages=endpoints[0].strip()+"-"+endpoints[1].strip()
					self.page=""
				else:
					self.page=self.page.strip()

	def getsource(self):
		if self.sourcematchers: self.sourcename=self.getdatum(self.sourcematchers)

	def gettitle(self):
		self.title=self.getdatum(self.titlematchers)
		self.titleclean()
		if self.toctext and self.sourcegroup=="Springer" and not self.pages:
			pagematch=re.search(re.escape(self.title)+"[\s\S]+?\<td class\=\"viewItem fontLarger\"[\s\S]+?\&nbsp\;(.*?)\s",self.toctext)
			if pagematch:
#				print self.title,pagematch.group(0)
				self.pages=pagematch.group(1).strip()

	def geturl(self):
		self.url=self.getdatum(self.urlmatchers)
		if self.urlcore:
			self.url=self.urlcore.replace("{{{match}}}",self.url)

	def getvolume(self):
		if self.volmatchers:
			self.volume=self.getdatum(self.volmatchers)
		elif self.toctext and self.sourcegroup=="Springer":
			volmatch=re.search("Volume (.*?), Number (.*?)\s",self.toctext)
			if volmatch: 
				self.volume=volmatch.group(1)
				self.issue=volmatch.group(2)

	def authorclean(self):
		self.author=self.author.strip()
		self.author=re.sub('\<sup\>.*?\<\/sup\>','',self.author)
		self.author=re.sub("\<[^\>]+\>","",self.author)
		if self.sourcename in self.author: self.author=""
		elif self.sourcey in self.author: self.author=""
		if self.authorcleaner: exec(self.authorcleaner)
		if self.sourcegroup=="Guardian":
			self.author=self.author.split(", ")[0].split(" in ")[0].strip()
		elif self.sourcegroup=="Science":
			authors=self.author.split("; ")
			authorparts=[]
			if len(authors)>2:
				authorparts=authors[0].split(", ")
				if len(authorparts)>1:
					self.author=authorparts[1].strip()+" "+authorparts[0].strip()+" et al."
				else:
					self.author=authorparts[0].strip()
			elif len(authors)==1 and len(authors[0].split(","))>2: #Nature uses commas only, no semicolons
				authors=self.author.split(",")
				if len(authors)>2: 
					self.author=authors[0].strip()+" et al."
				elif len(authors)==2:
					self.author=authors[0].strip()+" & "+authors[1].strip()
				else:
					try: self.author=authors[0].strip()
					except IndexError: 
						self.author=""
			elif len(authors)==2:
				authorparts1=authors[0].split(", ")
				authorparts2=authors[1].split(", ")
				try: self.author=authorparts1[1]+" "+authorparts1[0]+" & "+authorparts2[1]+" "+authorparts2[0]
				except IndexError: self.author=" ".join(authors)
			else:
				try: authorparts=authors[0].split(",")
				except IndexError: 
					self.author=""
				if len(authorparts)>1:
					self.author=authorparts[1].strip()+" "+authorparts[0].strip()
				else: 
					try: self.author=authors[0].strip()
					except IndexError: 
						self.author=""
		if self.sourcename=="New York Times":
			self.author=self.author.title() #Titlecasing

	def dateclean(self):
		self.date=re.sub("\<.*?\>","",self.date)
		if self.sourcename=="New York Times":
			dateparts=self.date.split(",")
			try: self.year=dateparts[1].strip()
			except IndexError: pass
			self.date=dateparts[0].strip()
		elif self.sourcegroup=="Guardian":
			try: parsedate=time.strptime(self.date,"%Y_%m_%d")
			except ValueError:
				parsedate=""
			if parsedate:
				self.date=time.strftime("%B %d",parsedate)
				self.year=time.strftime("%Y", parsedate)
		elif self.sourcename=="Toronto Star":
			dateparts=self.date.split(",")
			self.date=dateparts[0].replace("Jan ","January ").replace("Feb ","February ").replace("Mar ","March ").replace("Apr ","April ").replace("Jun ","June ").replace("Jul ","July ").replace("Aug ","August ").replace("Sep ","September ").replace("Oct ","October ").replace("Nov ","November ").replace("Dec ","December ").strip()  # Trailing space needed in order not to get fooled
			try: self.year=dateparts[1].strip()
			except IndexError:
				print dateparts
				self.year=str(datetime.date.today().year)
		elif self.sourcename=="Herald Sun":
			try: self.year=self.date.split(", ")[1][0:4]
			except IndexError:
				if not self.year: self.year=str(datetime.date.today().year)
			self.date=self.date.split(", ")[0]
		elif self.sourcename=="Chicago Reader":
			piecesofdate=self.date.split(", ")
			self.date=piecesofdate[0]
			try:
				self.year=piecesofdate[1]
			except IndexError:
				if not self.year: self.year="0000"
		elif self.sourcegroup=="Springer":
			if "-" in self.date:
				parsedate=time.strptime(self.date,"%Y-%m-%d")
				self.year=time.strftime("%Y",parsedate)
				self.date=time.strftime("%B %d",parsedate)
			else: 
				rawdate=self.date.strip().split()
				self.year=rawdate[2]
				self.date=rawdate[1]+" "+rawdate[0]
		elif self.sourcegroup=="Science":
			try: parsedate=time.strptime(self.date,"%m/%d/%Y")
			except ValueError:
				try: parsedate=time.strptime(self.date,"%Y-%m-%d")
				except ValueError:
					parsedate=""
			if parsedate:
				self.date=time.strftime("%B %d",parsedate)
				self.year=time.strftime("%Y", parsedate)
		self.date=self.date.replace(" 0"," ")
	def textclean(self): #Text cleanup for concordancing, after metadata has been extracted
		if self.includers:
			cleantext=re.search(self.includers,self.text)
			if cleantext:
				self.text=cleantext.group(1)
			else:
				if not self.skipincluders:
					self.text=""
		self.text=re.sub("(?i)\<[\/]*i\>","''",self.text)
		self.text=re.sub("(?i)\<[\/]*em\>","''",self.text)
	def titleclean(self):
		for g in self.goodtags:
				self.title=re.sub("(?i)\<"+g+".*?\>","&&!g",self.title)
				self.title=re.sub("(?i)\<\/"+g+".*?\>","!&&g",self.title)
		self.title=re.sub("\<[^\>]+\>","",self.title)
		for g in self.goodtags:
				self.title=re.sub("(?i)\&\&\!"+g,"<"+g+">",self.title)
				self.title=re.sub("(?i)\!\&\&"+g,"</"+g+">",self.title)
		self.title=self.title.strip()
		if self.titlecleaner: exec(self.titlecleaner)
	def verify_encoding(self,text):
		returnme=self.encoding
		if self.sourcename=="New York Times": #Style section sometimes in UTF-8, unmarked
			if "â€" in text: returnme="utf-8"
		return returnme


def getsourcedata(sourcey): 
	attributes={}
	journals=["Science","Nature","Notices of the American Mathematical Society","Lancet","Erkenntnis","Philosophical Studies","Journal of Pragmatics","Archives of Sexual Behavior"]
	aliases={
		"G":"The Guardian",
		"O":"The Observer",
		"Observer":"The Observer",
		"Guardian":"The Guardian",
		"NYT":"New York Times",
		"Reader":"Chicago Reader",
		"HS":"Herald Sun",
		"Star":"Toronto Star",
		"NAMS":"Notices of the American Mathematical Society",
		"CT": "Calcutta Telegraph",
		"PEH":"Port Elizabeth Herald",
		"AL":"Applied Linguistics",
		"JPrag":"Journal of Pragmatics",
		"PhilStud":"Philosophical Studies",
		"ASB":"Archives of Sexual Behavior"
	}
	sourcegroups={
		"The Guardian":"Guardian",
		"The Observer":"Guardian",
		"Nature":"Science",
		"Erkenntnis":"Springer",
		"Philosophical Studies":"Springer",
		"Archives of Sexual Behavior":"Springer",
	}
	attributes["headertemplate"]={
		"New York Times":"NYT_header",
		"The Observer":"Observer header",
		"The Guardian":"Guardian header",
		"Notices of the American Mathematical Society":"NAMS header",
		"Gutenberg":"Gutenberg header",
	}
	attributes["authormatchers"]={
		"New York Times": [
			"title=\"More Articles by (.*?)\"",
			"\<meta\s+name=\"byl\"\s+content=\"By\s+([^\"]*)",
			"\<h2\>By (.*?)\<\/h2\>"],
		"Guardian":["\<li class=\"byline\"\>([\s\S]*?)\<\/li\>"],
		"Herald Sun":["\<p class=\"author\"\>(.*?)\<\/p\>"],
		"Toronto Star":[
			"\<span id=.*?___Author1__\" class=\"articleAuthor\">([^<]*)", 
			'\<p class=\"authorByline\"\>([\s\S]*?)\<\/p'],
		"Chicago Reader":['\<meta name="author" content="(.*?)"'],
		"Science":["\<.*? name=\"citation_authors\" content=\"(.*)\""],
		"Springer":['\<p class=\"AuthorGroup\"\>(.*)\<\/p'],
	}
	attributes["datematchers"]={
		"New York Times": ["\<meta\s+name=\"DISPLAYDATE\"\s+content=\"([^\"]*)"],
		"Guardian": ["cv\.c7\=\"(.*?)\"\;"],
		"Herald Sun": ["\<p class=\"published-date\">(.*?)\<\/p\>"],
		"Toronto Star": [
			"\<span style=\"text-transform:capitalize;\"\> (.*?, \d+) .*",
			'\<span class=\"date\">([\s\S]*?)\<\/span'],
		"Chicago Reader": ['\<meta name="date" content="(.*?)"'],
		"Science":["\<.*? name=\"citation_date\" content=\"(.*)\""],
		"Springer":['\<strong\>Published online\: \<\/strong\>([^\<]*)'],
		"Notices of the American Mathematical Society":['\n([a-zA-Z]+\s[0-9]{4})\sNotices'],
	}
	attributes["pagematchers"]={
		"Nature":[
			"pageNumbers=[p]+([\d\-]+)",
			"\>[\d]+\<\/span\>,[\s\S]+?([\d\-]*)\n",
			"\/i\>[\s]*\<b\>[\d]+\<\/b\>,[\s]*([\d\-]+)[\s]*\("],
		"New York Times": ["\nPage ([\S]*)\r",
			"\<meta name\=\"print_page_number\" content\=\"(.*?)\""],
		"Science":["Home\<\/a\> .*? [\s\S]+?[p]+\.([\-\t\d\s\n\r]*[\d]+)\n"],
	}
	attributes["sourcematchers"]={ # Not relevant for most cases
		"Springer":["\<tr class=\"header\"\>[\s\S]*?\<td rowspan=\"1\" colspan=\"1\"\>([^\<]*?)\<"]
	}
	attributes["titlematchers"]={
		"New York Times": ["<meta\s+name=\"hdl\"\s+content=\"(.*?)\"","\<h1\>(.*?)\<\/h1\>"],
		"Guardian": ["\<h1\>(.*?)\<\/h1\>"],
		"Herald Sun": ["\<title\>(.*?)\|"],
		"Toronto Star":[
			"\<span id=.*?___Title__\" class=\"headlineArticle\">([^<]*)",
			"\<h4\>(.*?)\<\/h4"],
		"Chicago Reader":[
			'\<meta name=\"headline\" content=\"(.*?)\"\>', 
			'\<meta name=\"storytype\" content=\"(.*?)\"\>'],
		"Science":["\<.*? name=\"citation_title\" content=\"(.*)\""],
		"Springer":['\<a name=\"title\"\>\<\/a\>(.*)']
	}
	attributes["urlmatchers"]={ #Backup url-matching if the stamp is absent
		"New York Times": ["return encodeURIComponent\(\'(.*?\.html)\'\)\;"],
		"Guardian": ["\<url\>([^\<]*)"],
		"Herald Sun":[re.escape("http://digg.com/submit?phase=2&amp;url=")+"(.*?)\&amp\;"],
		"Toronto Star":["onclick=\"addthis_url = '(.*?)'"],
		"Chicago Reader":["\<title\>Reader Archive\-\-Extract\: (.*?)\<"],
		"Science": ["\<.*? name=\"citation_abstract_html_url\" content=\"(.*)\"", "\<.*? name=\"citation_.*?_url\" content=\"(.*)\""],
	}
	attributes["issuematchers"]={
		"Science":["\<.*? name=\"citation_issue\" content=\"(.*?)\""],
		"Notices of the American Mathematical Society":["9920\nVolume .*?, Number ([0-9]+?)\n"],
	}
	attributes["doimatchers"]={
		"Science":[
			"\<.*? name=\"citation_doi\" content=\"doi\:(.*?)\"", 
			"\<.*? name=\"citation_doi\" content=\"(.*?)\""],
		"Springer":[
			"\<title\>(.+?)\<\/title"],
	}
	attributes["volmatchers"]={
		"Science":["\<.*? name=\"citation_volume\" content=\"(.*?)\""],
		"Notices of the American Mathematical Society":["9920\nVolume (.*?), Number"],
	}
	attributes["replacers"]={ # Text to switch or remove before any extraction
		"New York Times": {"\<person[^\>]*?\>":""},
		"Herald Sun":{"\&squo\;":"'", "\>\>.*?\>\>":""},
		"Science": {"\|\[":"&","\]\|":";","(?i)\<[\/]*?STRONG\>":""},
		"Gutenberg":{
			"\[[A-Z]{1}[A-Za-z]+\:[^\]]*":" ", # Gutenberg uses e.g. "[Greek:" to mark transliterations
			"(?<=\W)\_":"''",
			"\_(?=\W)":"''",
			".*\t.*":"",
		}
	}
	attributes["includers"]={ # Article text
		"New York Times": '\<NYT\_TEXT.*([\s\S]*)\<\/NYT\_TEXT\>',
		"Guardian":'\<div id=\"article-wrapper\"\>([\s\S]*?)\<\/div\>',
		"Herald Sun": '\<div class=\"btm20\"\>([\s\S]*?)\<\/div\>',
		"Notices of the American Mathematical Society":"([\s\S]*)Degrees Conferred \n", #Avoid morass of non-delimited text	
		"Science":"([\s\S]+)\<\!\-\- END\: legacy HTML content \-\-\>",
		"Nature":"([\s\S]+)\<map title\=\"main journal navigation",
		"Gutenberg":"\*\*\*[\s]*START OF .*([\s\S]+)\*\*\*[\s]*END OF TH"
#		"Springer":"\<title\>([^\<]+)",
	}
	attributes["skipincluders"]={ #If there is no match for "includers", whether to include all text
		"Notices of the American Mathematical Society":True,
		"Gutenberg":True,
	}
	attributes["datecleaners"]={ # code to execute to scrub date
		"New York Times":'displaydate=datematch.group(1); dateparts=displaydate.split(", "); info.year=dateparts[1]; info.date=dateparts[0]',
		"Notices of the American Mathametical Society":'dateparts=datematch.group(1).split(" "); info.year=dateparts[1]; info.date=dateparts[0]',
	}
	attributes["titlecleaners"]={
#		"Science":"title=str(BeautifulSoup(title,convertEntities=BeautifulSoup.ALL_ENTITIES))"
		"Springer":"\<[\/]*i[^\>]*?\>"
	}
	attributes["getstring"]={ #non-overlapping regex to find the paragraphs of actual text
		"Nature":"(?i)(.*)\<P",
		"Science":"(?i)\<P([\s\S]*)\<[\/]*P",
		"Chicago Reader":"\<img.*?\>([\s\S]*?)\<br",
		"Springer":"\<p.*?\>([\s\S]*?)\<\/p"
	}
	attributes["encoding"]={
		"New York Times": "windows-1252",
		"Guardian":"utf-8",
		"Toronto Star": "utf-8",
		"Notices of the American Mathematical Society":"utf-8", 
	}
	attributes["authorsinpedia"]={
		"Chicago Reader": ["Cecil Adams","Jonathan Rosenbaum"],
		"New York Times": ["Maureen Dowd", "David Brooks","William Safire"]
	}
	attributes["urlcore"]={
		"Chicago Reader": "https://securesite.chireader.com/cgi-bin/Archive/abridged2.bat?path={{{match}}}",
	}
	attributes["noforeign"]={
		"Gutenberg":True,
	}
	attributes["nosinglequotes"]={
		"Gutenberg":True,
	}
	if sourcey in aliases.keys():
		source=aliases[sourcey]
	else:
		source=sourcey
	sourcedata=sourceobject()
#	print "Source: "+source
	sourcedata.sourcename=source
	if source in sourcegroups.keys():
		sourcedata.sourcegroup=sourcegroups[source]
#		print sourcedata.sourcegroup
	else:
		sourcedata.sourcegroup=source
	if sourcedata.sourcename in journals:
		sourcedata.sourcetype="journal"
	sourcedata.sourcey=sourcey
	for a in attributes:
		if sourcedata.sourcename in attributes[a].keys():
			sourcedata.__dict__[a]=attributes[a][sourcedata.sourcename]
		elif sourcedata.sourcegroup in attributes[a].keys():
			sourcedata.__dict__[a]=attributes[a][sourcedata.sourcegroup]
	if not sourcedata.headertemplate:
		sourcedata.headertemplate=source+"_header".replace("The ","")
	sourcedata.urlmatchers.extend(["\<url\>(.*?)\<\/url\>"])
	return sourcedata

def aggregate(path,source="",today=datetime.date.today(),learning=False,be_suspicious=False,nodump=True,upthis=False,lemmatise=False,tag=False):
	if tag:
		tagger=MontyTagger.MontyTagger()
	if lemmatise:
		lem=MontyLemmatiser.MontyLemmatiser()
	if path[-1]=="\\":
		path=path[:-1]
	sourcetype="news"
	enforce_paragraphs=False
	toctext=False
	sourcey=source
	if today==datetime.date.today() and not source:
		sourcey,today=getpathdata(path)
	if today.day:
		year=today.strftime("%Y")
		month=today.strftime("%m")
		day=today.strftime("%d")
	else:
		year=today.year
		month=today.month
		day=""
	if source=="":
		if sourcey=="G":
			source="The Guardian"
		elif sourcey=="O":
			source="The Observer"
		elif sourcey=="NYT":
			source="New York Times"
		elif sourcey=="Reader":
			source="Chicago Reader"
		elif sourcey=="HS":
			source="Herald Sun"
		elif sourcey=="Star":
			source="Toronto Star"
		elif sourcey=="NAMS":
			source="Notices of the American Mathematical Society"
			sourcetype="journal"
		elif sourcey=="PhilStud":
			source="Philosophical Studies"
			sourcetype="journal"
		else:
			source=sourcey
	header=""
	aggregator={}
	if not nodump:
		writefile=open(path+"\\"+"agg.txt","w") # force blank file
		writefile.write("")
		writefile.close()
	blankobject=sourceobject()
	files=os.listdir(path)
	filedata={}
	bookdata={}
	skippers=["firstfile.html","agg.txt","agg-log.txt","log.txt","candidates.txt","data.txt","raw.raw","raw.txt","cookies.lwp","toc.txt","toc.html"]
	if "data.txt" in files: # for  books etc., where metadata has to be added separately
		datafile=open(path+"\\data.txt","r")
		rawdata=datafile.read()
		bookdata["sourcetype"]="book" #default to book
		for line in rawdata.split("\n"):
			lineparts=line.split(":",1) # data file must be key:value pairs, separated by newlines
			if "filename" in lineparts[0]: continue # Don't need this.
			try: bookdata[lineparts[0].strip()]=lineparts[1].strip()
			except IndexError: continue
		datafile.close()
	if "toc.txt" in files:
		tocfile=open(path+"\\toc.txt","r")
		toctext=tocfile.read()
		tocfile.close()
	elif "toc.html" in files: 
		tocfile=open(path+"\\toc.html","r")
		toctext=tocfile.read()
		tocfile.close()
	for filename in files: #Read text from all eligible files in dir
		if "." not in filename: continue
		if ".pdf" in filename: continue
		if filename in skippers: continue
		thisdata=getsourcedata(source)
		thisdata.file=filename
		thisdata.toctext=toctext
		if thisdata.noforeign:
			mylid=lid.Lid()
		try:
			file=open(path+"\\"+filename)
		except IOError:
			print "Unable to open "+filename
			continue
		rawtext=file.read()
		if isspringer(rawtext) and not thisdata.sourcename:
			thisdata=getsourcedata("Springer")
		thisdata.text=rawtext
		file.close()
		if bookdata:
			thisdata.sourcename="Gutenberg"
			for b in bookdata.keys():
				thisdata.__dict__[b]=bookdata[b]
		if source=="New York Times":
			thisdata.enforce_paragraphs=True
		elif isspringer(rawtext):
			thisdata.getsource()
		elif source=="Notices of the American Mathematical Society":
			thisdata.pagefromcite="Notices\s*of\s*the\s*AMS\s*([0-9]{3}).*\n[\s\S]*?{{{passage}}}"
		thisdata.day=day
		thisdata.textprep()
		thisdata.path=path
		thisdata.getinfo()
		thisdata.textclean()
		if thisdata.headertemplate:
			if bookdata:
				header="{{User:Visviva/"+thisdata.headertemplate
				for b in bookdata.keys():
					header+="|"+b+"="+bookdata[b]
			else: 
				header="{{User:Visviva/"+thisdata.headertemplate+"|"+year+"|"+month+"|"
				if thisdata.day:
					header+=day
			if thisdata.day != datetime.date.today():
				header=header+"|creation="+datetime.date.today().strftime("%Y-%m-%d")
			header=header+"|status=uncleaned}}"
		getthis=thisdata.getstring
		if not re.search(getthis,thisdata.text): 
			if not thisdata.enforce_paragraphs:
				getthis="([\s\S]+)"
		filedata[thisdata.file]=copy(thisdata)
		aggregator=getparas(thisdata.text,aggregator,thisdata.file,getthis,thisdata.encoding)
		continue
	if not nodump:
		writefile=open(path+"\\"+"agg.txt","w") # Dump all processed text into one aggregated file
		for a in aggregator:
			writefile.write(a)
			continue
		writefile.close()
	stopwords=getstops()
	types=set()
	lctokens=0
	totalwords=0
	tokencount=0
	uniques=list()
	kwix={}
	data={}
	English=gettitles()
	Alltitles=getalltitles(English)
	Hot=set(open("D:\Code\hotlist.txt").read().split("\n"))
	Mist=gethotlist("D:\Code\\Missing")
	print len(aggregator)
	for ag in aggregator: #iterate through the globs of text extracted from each file
		if aggregator[ag] in filedata.keys():
			sentencedata=copy(filedata[aggregator[ag]])
#			sentencedata.text=''
		else: 
			print "No data for "+aggregator[ag]
			sentencedata=copy(blankobject)
		newuniques,newkwix,newdata,tokencount,lctokens,types=getconcordance(ag,sentencedata,English,uniques,stopwords,tokencount,lctokens,types,be_suspicious)
		uniques.extend(newuniques)
		kwix.update(newkwix)
		data.update(newdata)
		continue
	uniques.sort()
	if learning:
		return uniques
	ufile=open(path+"\\"+"candidates.txt","w")
	ufile.write(header+"\n\n")
	ufile.write("{{User:Visviva/wordhunt stats")
	ufile.write("\n|tokens="+str(tokencount))
	ufile.write("\n|goodtokens="+str(lctokens))
	ufile.write("\n|types="+str(len(types)))
	ufile.write("\n|newwords="+str(len(uniques))+"\n}}\n\n")
	try: 
		if not today==datetime.date(int(year),int(month),int(day)):
			isodate=year+"-"+month+"-"+day
		else: 
			isodate=today.isoformat()
	except ValueError:
		isodate=year+"-"+month
	ufile.write("=="+isodate+"==\n\n")
	the_string=""
	mylid_lang="English"
	sequestrables=[]
	sequestered=""
	for u in uniques:
		if not kwix[u]: continue
		wordline="[["+u+"]]"
		if u in Hot: wordline="'''"+wordline+"'''"
		if u in Mist: wordline="''"+wordline+"''"
		if u in Alltitles: 
			if data[u].noforeign: continue
			wordline+=" *"
		if data[u].noforeign:
			try: 
				try: 
					mylid_lang=mylid.checkText(kwix[u])
					if mylid_lang != "English": continue
				except ZeroDivisionError: pass
			except IndexError: pass
#			except IndexError: print kwix[u]
#			if mylid_lang != "English": 
#				sequestrables.append(u)
		wordline="# "+wordline
		citationtemplate="{{User:Visviva/quote-"+data[u].sourcetype+"-special"
		if tag:
			pos_raw=MontyPos(tagger.tag(kwix[u].strip().replace("'''","")),u)
			pos=pos_raw.split(",")[0]
		else: pos,pos_raw="",""
		pagetitle=u
		if mylid_lang != "English":
			wordline += " (LID: possibly "+mylid_lang+")"
		elif "," in pos_raw and lemmatise:
			pagetitle=lem.lemmatise_word(u)
			if pagetitle != u: 
				wordline+=" -> [["+pagetitle+"]]"
		if data[u].sourcetype=="journal":
			citationstring=wordline+"\n#*"+citationtemplate+"|pagetitle="+pagetitle+"|year="+data[u].year+"|date="+data[u].date+"|author="+data[u].author+"|title="+data[u].title+"|work="+source+"|doi="+data[u].doi+"|volume="+data[u].volume+"|issue="+data[u].issue+"|pos="+pos
			if data[u].url:
				citationstring+="|url="+data[u].url
			if data[u].pages:
				citationstring+="|pages="+data[u].pages
			if data[u].page:
				citationstring+="|page="+data[u].page
			citationstring=citationstring+"\n|passage="+kwix[u].strip()+" }}\n"
		else:
			if data[u].sourcetype=="book":
				citationstring=wordline+"\n#*{{User:Visviva/quote-book-special|pagetitle="+pagetitle
				for b in bookdata:
					citationstring+="|"+b+"="+bookdata[b]
				citationstring+="|pos="+pos+"\n|passage="+kwix[u].strip()+"}}\n"
				citationstring=citationstring.replace("{{{file}}}",data[u].file.split(".")[0])
			elif "Lancet" in source or data[u].sourcename=="":
				citationstring=wordline+"\n#:''"+kwix[u].strip()+"''\n"
			else:
				citationstring=wordline+"\n#*"+citationtemplate+"|pagetitle="+pagetitle+"|year="+data[u].year+"|date="+data[u].date+"|author="+data[u].author+"|title="+data[u].title+"|work="+source+"|url="+data[u].url+"|pos="+pos
				if data[u].page:
					citationstring=citationstring+"|page="+data[u].page
				citationstring=citationstring+"\n|passage="+kwix[u].strip()+"}}\n"
#			if u in sequestrables:
#				sequestered+=citationstring
#			else:
		the_string+=citationstring
	ufile.write(the_string)
	ufile.write("\n===Sequestered===\n\n")
#	ufile.write(sequestered)
	ufile.close()
	if actiondir:
		actionfilename=os.path.split(path)[1]+"_candidates.txt"
		os.system("fsutil hardlink create "+actiondir+"\\"+actionfilename+" "+path.replace("\\\\","\\")+"\candidates.txt")
	if upthis: #Must be Wikipedia Page object
		if upthis==True:
			frakt=wikipedia.getSite("en","fraktionary")
			wikt=wikipedia.getSite("en","wiktionary")
			wikt_page=wikipedia.Page(wikt,"User:Visviva/"+os.path.split(path)[1].replace("-",""))
			frakt_page=wikipedia.Page(frakt,"List:"+os.path.split(path)[1].replace("-",""))
			oneup(path,wikt_page)
			oneup(path,frakt_page)
		else:
			oneup(path,upthis)
	homework=open(scriptdir+"\\homework.txt","a") # To be put into the daily stopword-acquisition cycle
	homework.write("\n"+path)

def getparas(rawtext,aggregator,filename,getstring="(.*)",encoding="iso-8859-1"): # grabs paragraphs using either a standard pattern or a custom one
	verybadtags=["script","style","object","iframe"]
	for v in verybadtags:
		rawtext=re.sub("(?i)\<"+v+"[\s\S]*?\<\/"+v+"\>","",rawtext)
	rawtext=re.sub("\<\!\-\-[\s\S]*?\-\-\>","",rawtext)
	for m in re.finditer(getstring,rawtext):
		try: n=m.group(1)
		except IndexError: continue
		aggregator[n]=filename
		continue
	return aggregator

def gettitles(): # grabs titles from file
	English=[]
	listfile=open(scriptdir+"\\en_titles.txt","r")
	for l in listfile:
		English.append(l.strip())
	English.sort()
	return English

def getalltitles(English=set()): # grabs titles from file
	Alltitles=set()
	Alltitles=set([x.strip() for x in open(scriptdir+"\\all_titles.txt","r").read().split("\n")])
#	print "Alltitles done."
	return Alltitles

def getstops(): # grabs stopwords from file
	stopfile=open(scriptdir+"\\stop.txt","r")
	stopwords=set()
	for s in stopfile:
		stopwords.add(s.strip())
		continue
	return stopwords

def badbreak(sentence,next=""): # checks whether the next block is actually part of the same sentence.
	sentence=sentence.strip()
	next=next.strip()
	neverbreaks=["vs.","e.g.", "e. g.","i.e.","i. e.","Mr.","Mrs.","Dr.","Prof.","Ms.","Sen.","Rep.","fig.","figs.","Fig.","Figs."]
	for n in neverbreaks:
		try: 
			if sentence[-len(n):]==n or next[:len(n)]==n: 
				return True
		except IndexError: continue
	alwaysbreaks=["“"]
	for a in alwaysbreaks:
		try: 
			if next[:len(a)]==a: 
				return False
			elif sentence[-len(a):]==a:
				return len(a)
		except IndexError: continue
	if next=="": return False
	try: lastchar=sentence[-1]
	except IndexError: return False
	if next[0]=="," or next[0]==";" or next[0]==":": return True
	try: 
		if re.match("[a-z]",next):
			return True
	except IndexError: pass
	maths=sentence.split("&&math&&") #Avoid breaking in middle of math expression
	if len(maths)>1:
		if "&&/math&&" not in maths[len(maths)-1]:
			return True
	if lastchar=="." and len(sentence)>2:
		if re.match("\d",next):
				return True
		elif re.match(".*[A-Z][a-z]{0,2}\.",sentence.split(" ")[len(sentence.split(" "))-1]) or re.match("[A-Z]",sentence[-2]) or re.match("[A-Z][a-z]\.",sentence[-3:]):
			return True
	return False


def getpathdata(path): #gets date and source alias  from name of a directory in the form "<source alias>_<date>"
	today=datetime.date.today()
	pathparts=path.split("\\")
	sourcey=""
	dirparts=pathparts[len(pathparts)-1].split("_")
	if len(dirparts)==2:
		sourcey=dirparts[0]
		datey=dirparts[1]
		if len(datey)==10:
			todayraw=time.strptime(datey,"%Y-%m-%d")
			today=datetime.date(todayraw.tm_year,todayraw.tm_mon,todayraw.tm_mday)
		elif len(datey)==8: 
			try: 
				todayraw=time.strptime(datey,"%Y%m%d")
				today=datetime.date(todayraw.tm_year,todayraw.tm_mon,todayraw.tm_mday)
			except ValueError: pass
		elif len(datey)==6:
			todayraw=time.strptime(datey,"%Y%m")
			today=ufo()
			today.year=str(todayraw.tm_year)
			today.month=str(todayraw.tm_mon)
			if len(today.month)==1: today.month="0"+today.month
			today.day=""
	print sourcey,today
	return sourcey,today


def getconcordance(ag="",sentencedata=sourceobject(),English=set(),uniques=[],stopwords=set(),tokencount=0,lctokens=0,types=[],be_suspicious=False):
#	ag=ag.decode("utf-8")
	print sentencedata.file
	ag=re.sub("\<a[^\>]+\>","", ag)
	ag=re.sub("\<img .*? alt=\"\$\$(?P<group>[^\"]*?)\$\$\"[^>]*?\>","&&math&&\g<group>&&/math&&",ag) # Math text for Springer
	ag=ag.replace(".&&/math&&","&&/math&&.") #Prevent periods from being caught inside <math>
	ag=re.sub("\<img[^\>]+\>"," ",ag)
	ag=re.sub("[\n\r\t]+"," ",ag) #Trim down whitespace
	x=0
	closequote=unicode("”",encoding='utf-8')
	closequoteparts=""
	for x in range(len(closequote)):
		closequoteparts+=re.escape(closequote[x].encode("utf-8"))
	openquote=unicode("“",encoding='utf-8')
	openquoteparts=""
	for x in range(len(openquote)):
		openquoteparts+=re.escape(openquote[x].encode("utf-8"))
	pieces=re.split("([\.\?\!\|]+[\"\'\)\]\’"+closequoteparts+openquoteparts+"]*\s*)",ag)
	sentences=[]
	newuniques=[]
	newkwix={}
	newdata={}
	for p in pieces: #Recombine sentences, separators
#		p=p.encode("utf-8")
		if x%2:
			sentences.extend([pieces[x-1]+p])
		x+=1
	sentences.extend([pieces[len(pieces)-1]])
	x=0
	for s in sentences:
		rawsentence=s
		x+=1
		try: next=sentences[x]
		except IndexError: next=""
		try: 
			while re.match("[\)\]\’]",next.strip()[0]): #cleanup 
				s+=next[0]
				sentences[x]=next[1:]
				next=sentences[x]
		except IndexError: pass
		while badbreak(s,next):
			status=badbreak(s,next)
			if type(status)==int:
				try: 
					sentences[x]=s[-status:]+next
					s=s[:-status]
				except IndexError:
					break
				next=sentences[x]
				continue
			s+=next
			try: sentences.remove(sentences[x])
			except IndexError: break
			try: next=sentences[x]
			except IndexError: break
		if len(s) > 2000: continue # Avoid super-bloat.
		sentence=s
		sentence=re.sub("\<[^\>]*\>"," ",sentence) # Throw out any tags in KWIC line
		sentence=sentence.replace("&&math&&","<math>")
		sentence=sentence.replace("&&/math&&","</math>")
		sentence=sentence.replace("|","{{!}}") # Make template-safe
		s=" ".join(re.split("[a-z\/\:\.\%\+]*\.[a-z][a-z\s\/\_\?\=\.\-\&\%\+]+",s)) # remove web addresses, even if they have spaces
		s=" ".join(re.split("(?i)\<i.*?\>[\s\S]*?\<\/i\>",s)) # remove anything in italics
		s=re.sub("(?i)\<em\>[\s\S]*?\<\/em\>"," ",s)
		s=re.sub("\W\'\'[^\']+\'\'"," ",s)
		s=re.sub("\<span style=\"font-style\: italic;\"\>.*?\<\/span\>"," ",s) # especially annoying fancy ones
		s=re.sub("\<span class=\"italic\"\>[^\>]*"," ",s) 
		s=" ".join(re.split("\<[^\>]*\>",s)) # Now, remove all tags
		s=" ".join(re.split("\S*@[^A-Z]*",s)) # remove emails, and anything until the next capitalized word
		s=" ".join(re.split("\S*\{at\}[^A-Z]*",s)) # remove obfuscated emails
		s=" ".join(re.split("\w*[\-\'\’]+\w*",s)) # remove hyphenated and apostrophated words
		words=re.split("[\s"+re.escape(punctuation)+"]+",s)
		if len(words) < 2: continue
		y=0
		badwords=["com","org","gov","uk","ca","au","nl","fr"]
		for word in words:
			word=word.strip()
			tokencount+=1
			if not word.islower() or word in stopwords:
				y=y+1
				continue
			if re.search("[^a-z]+",word):  # Currently throws out all words with diacritics
				y=y+1
				continue
			if not re.search("[aeiouy]+",word): # No vowels -- bad sign
				y=y+1
				continue
			if word in English or word in uniques or word in newuniques: #skip time-consuming stuff if word is unlikely to be useful
				continue
			try: 
				if words[y+1].strip() in badwords : # Any extra domain names that weren't filtered out above for any reason (spacing etc.)
					y=y+1
					continue
				if words[y-1]+" "+word in English or word+" "+words[y+1] in English:
					y=y+1
					continue
			except IndexError: 
				pass
			if be_suspicious:
				if issuspicious(word,words,y,English):
					y=y+1
					continue
			w=word.strip()
			lctokens+=1
			types.add(w)
			if w not in English and w not in uniques and w not in newuniques:
				if y>0 and words[y]==w and re.match("[A-Z]{1} ",words[y-1]+" "): # Has the first letter of a sentence been split off?
					y+=1
					continue
				if (words[y-1]+w).lower() in English or words[y-1]+w in English:
					y=y+1
					continue
				if re.match("(?i)[IVXLDCM]+ ",word+" "):
					print "Roman numeral: "+word
					continue
				newuniques.append(w)
				if sentencedata.pagefromcite:
					pagefromcite=sentencedata.pagefromcite.replace("{{{passage}}}",re.escape(w))
					pagematch=re.search(pagefromcite,sentencedata.text)
					if not pagematch: 
						print "No page for "+word
					else: 
						sentencedata.page=pagematch.group(1)
				sentence_ready=re.sub("(?<=\W)"+re.escape(w)+"(?=\W)","'''"+w+"'''",sentence)
				newkwix[w]=re.sub("[\n\r\t\s]+"," ",sentence_ready)
				newdata[w]=copy(sentencedata)
				y=y+1
			continue
		continue
	return newuniques,newkwix,newdata,tokencount,lctokens,types

def issuspicious(word,words,y,English):
	try: 
		if word+words[y+1].strip() in English or words[y-1].strip()+word in English:
			return True
		z=0
		for letter in word:
			if word[:z] in English and word[z:] in English:
				return True
			z=z+1
	except IndexError:
		return False
	return False


def learn(path):
	if "\\" not in path: return False
	print "Learning from "+path+"..."
	unchecked=aggregate(path,learning=True)
	try: checkedfile=open(path+"\\candidates.txt","r")
	except IOError: return False
	checkedtext=checkedfile.read()
	checkedfile.close()
	checked=[]
	added=[]
	stopfile=open(scriptdir+"\\stop.txt","r")
	allthestops=stopfile.read()
	stopfile.close()
	stoplist=re.split("[\r\n\s]+",allthestops)
	for chunk in checkedtext.split("\n#"):
		if "{" in chunk.split("\n")[0]: continue
		checkmatch=re.match("[\s\']*\[\[([^\]]+?)\]\]",chunk)
		if checkmatch:
			checked.extend([checkmatch.group(1)])
	for u in unchecked:
		if u in stoplist: continue
		if u in checked: continue
		stoplist.extend([u])
		added.extend([u])
	stoplist.sort()
	logfile=open(scriptdir+"\\stoplog.txt","a")
	logfile.write("\n\n"+str(datetime.date.today())+"\n"+path+"\n"+str(added))
	stopfile=open(scriptdir+"\\stop.txt","w")
	stopfile.write("\n\n")
	for s in stoplist:
		if not s.strip(): continue
		stopfile.write(s+"\n")
	stopfile.close()
	logfile.close()
	return added


def learnfromfile():
	return True #Cut off for now.
	file=open(scriptdir+"\\homework.txt","r")
	list=file.read()
	file.close()
	done=set()
	for l in list.split("\n"):
		path=l.strip()
		if path in done:
			continue
		done.add(path)
		try: learn(path)
		except IOError: continue
	blankthis=open(scriptdir+"\\homework.txt","w")
	blankthis.write("")
	blankthis.close()


def cleanstops():
	English=gettitles()
	newstoplist=set()
	removed=set()
	stopfile=open(scriptdir+"\\stop.txt")
	stoplist=stopfile.readlines()
	for s in stoplist:
		if s.strip() not in English: newstoplist.add(s.strip())
		else: removed.add(s.strip())
	removed=list(removed)
	newstoplist=list(newstoplist)
	removed.sort()
	newstoplist.sort()
	stopfile.close()
	writefile=open(scriptdir+"\\stop.txt","w")
	for n in newstoplist:
		writefile.write("\n"+n)
	logfile=open(scriptdir+"\\stoplog.txt","a")
	logfile.write("\n\n"+str(datetime.date.today())+"\nRemoved:\n"+str(removed))


def isspringer(text):
	match=re.search('\<a name=\"title\"\>\<\/a\>',text)
	if match:
		return True
	else: 
		return False


def titlegrabber(lang="English"):
	import xmlreader
	totalfile=open(scriptdir+"\\all_titles.txt","w")
	writefile=open(scriptdir+"\\en_titles.txt","w")
	English=set()
	all=set()
	if "wikt.xml" not in os.listdir(scriptdir):
		dump=xmlreader.XmlDump(scriptdir+"\wikt.bz2")
	else:
		dump=xmlreader.XmlDump(scriptdir+"\wikt.xml")
	for d in dump.parse():
		all.add(d.title)
		if ":" in d.title: continue
		elif "=="+lang+"==" not in d.text: continue
		else: English.add(d.title)
	for e in English:
		writefile.write(e.encode("utf-8")+"\r\n")
	for a in all:
		totalfile.write(a.encode("utf-8")+"\r\n")
	writefile.close()
	totalfile.close()

def defgrabber(lang="English",limit=0):
	import xmlreader
	totalfile=open(scriptdir+"\\all_titles.txt","w")
	writefile=open(scriptdir+"\\en_titles.txt","w")
	English=set()
	if "wikt.xml" not in os.listdir(scriptdir):
		dump=xmlreader.XmlDump(scriptdir+"\wikt.bz2")
	else:
		dump=xmlreader.XmlDump(scriptdir+"\wikt.xml")
	for d in dump.parse():
		if "==%s==" % lang not in d.text: continue
		sects=d.text.split('----')
		section=[x for x in sects if "==%s==" % lang in x][0]
		defs=re.findall("\#[^\*\:].+",section)
		for defn in defs: English.add((d.title,defn))
	English=list(English)
	if limit:
		English=English[:limit]
	English.sort()
	diction={}
	for e in English:
		if e[0] not in diction.keys():
			diction[e[0]]=[e[1]]
		else:
			diction[e[0]].append(e[1])
	return diction


def bestconc(word,text,knownwords=set(),limit=10,delim="[\.\?\!\n]"):
	text="\n"+text+"\n"
	concs=re.findall("(?<="+delim+").*?\W"+word+"\W.*?"+delim,text)
	ranked=[]
	for c in concs:
		score=25
		concwords=[x.lower() for x in re.split("\W+",c)]
		if len(concwords) < 4: continue #probably not an adequate sentence
		if len(concwords) > 5:
			score-=len(concwords)-4
		score+=len(set(concwords).intersection(set(knownwords)))
		score-=len([x for x in concwords if len(x)>5])
		if score > 0: 
			ranked.append((score,c))
	ranked.sort()
	ranked.reverse()
	return ranked[:limit]

def trackinglist(dir=scriptdir+"\\Tracking",cutoff=3):
	Hot=gethotlist()
	Mist=gethotlist("D:\Code\\Missing")
	linxin=dict()
	English=gettitles()
	stoppers=[] # For words that need to be thrown out before next update
	skippers=["wanted.txt","Tracking","Wanted","firstfile.html","Hotlist"]
	dirlist=os.listdir(dir)
	for filename in dirlist:
		if filename in skippers: continue
		text=open(dir+"\\"+filename).read().split("Sequestered</span></h3>")[0]
		inpage=set()
		for match in re.finditer('"\/w\/index\.php\?title\=(.*?)\&amp\;action\=edit',text):
			pagename=match.group(1).strip()
			if pagename in inpage: continue # avoid double-counting any accidental duplicates
			else: inpage.add(pagename)
			if pagename in English or pagename in stoppers or ":" in pagename: continue
			elif pagename in linxin: linxin[pagename]+=1
			else: linxin[pagename]=1
	wanted = [ (value, key) for key, value in linxin.iteritems() ]
	wanted.sort()
	wanted.reverse()
	resultfile=open(dir+"\\wanted.txt","w")
	result="As of "+datetime.date.today().isoformat()+"  <small>[http://en.wiktionary.org/w/index.php?title=User:Visviva/Tracking/Wanted&action=edit edit]</small>"
	result+=" - Lists checked: "+str(len(dirlist)-len(skippers))
	result+=" - Unique missing words: "+str(len(linxin))+"\n\nWords on the [[User:Brian0918/Hotlist|Hotlist]] are in bold; words on Robert Ullmann's [[User:Robert Ullmann/Missing|Missing]] list are in italics.\n"
	lastnum=0
	for w in wanted: 
		if w[0] >= cutoff and w[0] not in stoppers:
			if w[0] != lastnum:
				result+="\n* "
			lastnum=w[0]
			linkstring="[["+w[1]+"]]"
			if w[1] in Hot: linkstring="'''"+linkstring+"'''"
			if w[1] in Mist: linkstring="''"+linkstring+"''"
			linkstring+=" ([[Special:Whatlinkshere/"+w[1]+"|"+str(w[0])+"]])"
			result+=linkstring+" - "
	resultfile.write(result)
	resultfile.close()
	if actiondir:
		actionfilename="wanted.txt"
		os.system("fsutil hardlink create "+actiondir+"\\"+actionfilename+" "+dir.replace("\\\\","\\")+"\wanted.txt")


def gethotlist(hotlistdir="D:\Code\\Tracking\\Hotlist"): 
	hotlist=set()
	for filename in os.listdir(hotlistdir):
		linksinfile=0
		text=open(hotlistdir+"\\"+filename).read()
		for match in re.finditer ('\<li\>\<a href\=\"\/w\/.*?class\=\"new\".*?\>(.*?)\<\/a\>',text):
			linksinfile+=1
			hotlist.add(match.group(1).strip())
#	print "Hotlist length: "+str(len(hotlist))
	return hotlist


def batchup(dir="D:\Action",prefix="User:Visviva/"):
	import wikipedia
	site=wikipedia.Site("en","wiktionary")
	for o in os.listdir(dir):
		if "_candidates" not in o: continue
		pagename=o.split("_cand")[0].replace("-","")
		print pagename
		sourcey=pagename.split("_")[0]
		print sourcey, getsourcedata(sourcey).sourcename
		pagename=prefix+pagename.replace(sourcey,getsourcedata(sourcey).sourcename)
		print pagename
		page=wikipedia.Page(site,pagename)
		text=unicode(open(os.path.join(dir,o)).read(),encoding="utf-8",errors="ignore")
		print len(text)
		page.put(text,"Batch upload of tracking lists",True,True)
		time.sleep(30)


def oneup(path,page):
		text=open(path+"\\"+"candidates.txt").read()
		if "fraktionary" in str(page.site()):
			text=text.replace("{{User:Visviva/","{{")
		text=unicode(text,encoding="utf-8",errors="ignore")
		page.put(text)


def MontyPos(text,keyword): #Gets POS for keyword from tagged sentence produced by MontyTagger
	tags={
			"CC":"Conjunction",
			"CD":"Number",
			"DT":"Determiner",
			"EX":"Existential",
			"FW":"Foreign",
			"IN":"Preposition",
			"JJ":"Adjective",
			"JJR":"Adjective, comparative",
			"JJS":"Adjective, superlative",
			"LS":"List item marker",
			"MD":"Verb",
			"NN":"Noun",
			"NNS":"Noun, plural",
			"NP":"Noun",
			"NNP":"Noun",
			"NPS":"Noun, plural",
			"PDT":"Determiner",
			"POS":"Possessive ending",
			"PP":"Pronoun",
			"PRP":"Pronoun",
			"PP$":"Pronoun",
			"RB":"Adverb",
			"RBR":"Adverb, comparative",
			"RBS":"Adverb, superlative",
			"RP":"Particle",
			"SYM":"Symbol",
			"TO":"to",
			"UH":"Interjection",
			"VB":"Verb",
			"VBD":"Verb, past tense",
			"VBG":"Verb, gerund or present participle",
			"VBN":"Verb, past participle",
			"VBP":"Verb, non-3rd person singular present",
			"VBZ":"Verb, 3rd person singular present",
			"WDT":"Determiner",
			"WP":"Pronoun",
			"WP$":"Pronoun",
			"WRB":"Adverb",
	}
	try: tag=text.split(keyword+"/",1)[1].split(" ",1)[0].strip()
	except IndexError: return ""
	try: pos=tags[tag]
	except KeyError:
		print "No tags for "+keyword,tag,text
		return ""
	return pos


def unescape(text): 
#From code by Fredrik Lundh at http://effbot.org/zone/re-sub.htm#unescape-html
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
