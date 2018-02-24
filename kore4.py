import datetime
import os
import re
import time
import urllib
import urllib2


dirr="C:\\Code\\Naver"

def naverextract(text):
	title=text.split("<title>")[1].split(":")[0].strip()
	if "'" in title:
		title=title.split("'")[1].split("'")[0].strip()
	pieces=text.split('<SPAN class="EQUIV">')[1:]
	pieces=[x.split("</span>")[0] for x in pieces]
	pieces=[re.sub("\<.*?\>","",x) for x in pieces]
	pieces=[re.sub("[\<\(\,\[\r\n].*","",x) for x in pieces]
	glosses=[x.strip() for x in pieces]
	return title,glosses
	
	
def naverextract_ko(text):
	pass
	
	
def naverloop(directory=dirr):
	files=os.listdir(directory)
	files=[os.path.join(directory,x) for x in files if "G" not in x] # skip Googley files
	outlines=[]
	for f in files:
		stamp=f.split("\\")[-1].split(".")[0]
		print stamp
		text=open(f).read()
		if not text: continue
		title,glosses=naverextract(text)
		outlines.append(stamp+"\t"+title+"\t"+", ".join(glosses))
		print stamp,str(glosses)
	return outlines
	
def googleextract(text):
	catchstring1='<meta name="description" content="'
	catchstring2="- Google"
	if catchstring1 not in text: 
		return "",""
	caught=text.split(catchstring1)[1].split(catchstring2)[0].strip()
	if '"' in caught: caught=caught.split('"')[0].strip()
	if ":" not in caught: 
		return "",""
	title=caught.split(":")[0].strip()
	glosses=caught.split(":")[1].split(";")
	glosses=[x.strip() for x in glosses]
	return title,glosses
	
def googloop(directory=dirr):
	files=os.listdir(directory)
	files=[os.path.join(directory,x) for x in files if "G" in x] # Googles only
	outlines=[]
	for f in files:
		stamp=f.split("\\")[-1].split(".")[0]
		print stamp
		text=open(f).read()
		if not text: continue
		title,glosses=googleextract(text)
		outlines.append(stamp+"\t"+title+"\t"+", ".join(glosses))
		print stamp,str(glosses)
	return outlines

def list2voc(path="C:\\Code\\koreanvocab2.txt"):
	import pie
	vocab=pie.Vocabulary(filter=False,language="Korean")
	text=open(path).read()
	text=text.decode("utf-8","ignore")
	lines=text.split("\n")
	lines=[tuple(x.split("\t")) for x in lines if "\t" in x]
	for line in lines:
		rank=line[0]
		print rank.encode('utf-8','ignore')
		if rank:
			try:
				tally=1000000/int(rank)
			except:
				tally=0
		else:
			tally=0
		word=line[1]
		newword=pie.Word(text=word)
		newword.tally=tally
		vocab.allwords.add(newword)
	return vocab
	
def combine(file1,file2):# TSV of CSV glosses
	dixie={}
	dixie2={}
	for line in file1.split("\n"): #files come in as text, not handles
		parts=line.split("\t")
		dixie[parts[1]]=[x.strip() for x in parts[2].split(",") if x.strip()]
	for line in file2.split("\n"):
		parts=line.split("\t")
		if parts[1] in dixie.keys():
			dixie[parts[1]].extend([x.strip() for x in parts[2].split(",") if x.strip()])
		else:
			dixie[parts[1]]=[x.strip() for x in parts[2].split(",") if x.strip()]
	for d in dixie.keys():
		newlist=[]
		newlist2=[]
		countlist=[]
		for i in dixie[d]:
			newlist.extend([x.strip() for x in re.split("[^a-zA-Z0-9\-\s]+",i) if x])
		for n in newlist:
			testers=["a","an","the","to"]
			for t in testers:
				if (n.startswith(t+" ") or n.startswith(t.title()+" ")) and len(n) > 1+len(t):
					n=n[len(t):].strip()
					break
			newlist2.append(n)
		countlist=list(set((newlist2.count(x),x) for x in newlist2))
		countlist.sort()
		countlist.reverse()
		dixie[d]=newlist2
		dixie2[d]=countlist
	return dixie,dixie2
			
			
def get_naver_en(word):
	pass

def get_naver_ko(word):
	import urllib, urllib2
	url="http://krdic.naver.com/search.nhn?dic_where=krdic&query=%s&kind=keyword" % urllib.quote(word)
	page=urllib2.urlopen(url,timeout=60).read()
	matcher=re.escape('<a class="fnt15" href="') + '([^\"]*)' + re.escape('"><strong>') + '([^\<]*)' + re.escape('</strong><') # trailing "<" excludes partial headword matches
	pieces=re.findall(matcher,page)
	defs=[]
	for p in pieces: # keep this simple for now; don't bother actually chasing to next page
		if word not in p:
#			print "No words!"
			continue
		else:
#			print "Yay!"
			pass
		try:
			chunk=page.split(p[0])[1].split("<p>")[1].split("<div")[0].split("<p")[0]
		except Exception, e:
			print "Caught",e
			continue
		chunk=re.sub("\<[^\>]*\>","",chunk)
		chunk=chunk.replace("&lt;","<").replace("&gt;",">")
		lines=[x.strip() for x in chunk.split("\n") if x.strip()]
		defs.append("  /  ".join(lines))
	return defs
		
def naver_ko_loop(inpath,outpath="",directory="C:\\Code"):
	if not outpath:
		outpath=os.path.join(directory,"testdefs-"+datetime.date.today().isoformat()+".txt")
	words=open(inpath).read().split("\n")
	output=""
	words=[x.strip() for x in words if x.strip()]
	print len(words)
	for w in words:
		done=False
		print words.index(w)
		while not done:
			try:
				defs=get_naver_ko(w)
				time.sleep(1)
			except Exception, e:
				print str(e)
				time.sleep(5)
				continue
			done=True
		if defs:
			defstring=" //  ".join(defs)
			output+=w+"\t"+defstring+"\n"
		else:
			output+=w+"\t\n"
	if outpath:
		try:
			open(outpath,"w").write(output)
			print outpath
		except Exception, e:
			print str(e)
	outdefs=dict([tuple(x.split("\t")) for x in output.split("\n") if x.strip()])
	return outpath,outdefs
	
def get_examples_naver(word,kill_html=True): #UTF8-encoded hangul string
	url="http://krdic.naver.com/search.nhn?kind=all&scBtn=true&query="+urllib.quote(word)
	print url
	output=[]
	done=False
	while not done:
		try:
			page=urllib2.urlopen(url).read()
			done=True
		except Exception, e:
			print e
			continue
	try:
		section=page.split('<span class="head_ex">')[1].split("</ul>")[0]
	except IndexError, e:
		print str(e)
		return output
	lines=section.split("<li>")[1:]
	lines=[x.split("<p>")[1].split("<span class")[0].strip() for x in lines]
	if kill_html:
		lines=[re.sub("\<[^\<]*\>","",x) for x in lines]
	return lines
