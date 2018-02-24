import re, os

dir="C:\\Code\\Naver"

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
	
def naverloop(directory=dir):
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
#	colonics=[x for x in glosses if ":" in x]
	return title,glosses
	
def googloop(directory=dir):
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
