# -*- coding: utf-8 -*-

import datetime
from htmlentitydefs import name2codepoint
import os
import random
import re
import threading
import time
import urllib2
import urllib
import unicodedata

# -- Third-party modules -- #

import wx
import wx.lib.scrolledpanel
from wx.html import HtmlWindow
wx.SetDefaultPyEncoding("utf-8")

import matplotlib
matplotlib.use( 'WXAgg' )

# -- internal imports -- #

import pie

# -- globals and such -- #

try:
	workingdir=os.path.dirname( os.path.realpath( __file__ ) ) # doesn't work when compiled...
except:
	workingdir="."

# -- interface objects -- #

class ManagerWindow(wx.Frame):
	def __init__(self,vocab,direction=1,loadsource=""):
		print "Creating manager window"
		self.cardvocab=vocab
		random.shuffle(self.cardvocab.words)
		language=vocab.language
		wx.Frame.__init__(self, None, wx.ID_ANY, "LanguagePie Vocabulary Manager for %s, learning %s" % (str(vocab.user),vocab.language))
		self.Maximize()
		self.CreateStatusBar()
		self.tabs=wx.Notebook(self, -1,wx.Point(0,0), wx.Size(0,0), style=wx.NB_FIXEDWIDTH|wx.NB_RIGHT)
		iconpath=os.path.join(workingdir,"picon2.ico")
		if "picon2.ico" in os.listdir(workingdir):
			self.icon = wx.Icon(iconpath, wx.BITMAP_TYPE_ICO)
			self.SetIcon(self.icon)
		self.cardvocab.quickfind['']=pie.Word() # tofix
		self.testing=False
		self.color = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE)
		self.color_floats = tuple([float(x)/255.0 for x in self.color])
		self.wordfont=wx.Font(35,wx.DEFAULT,wx.NORMAL,wx.NORMAL)
		self.wordfont_small = wx.Font(20,wx.DEFAULT,wx.NORMAL,wx.NORMAL)
		self.examplefont = wx.Font(15,wx.DEFAULT,wx.NORMAL,wx.NORMAL)
		self.littlefont = wx.Font(8,wx.DEFAULT,wx.NORMAL,wx.NORMAL)
		self.language=vocab.language
		self.direction=direction
		self.fliptime = time.time()
		self.sessiondirection = direction
		self.loadsource = loadsource
		self.currentdir = os.getcwd()
		self.wordboxes = dict([(x,False) for x in self.cardvocab.words])
		self.cardpanel = wx.Panel(self.tabs, wx.ID_ANY)
		self.panel2 = wx.Panel(self.tabs, wx.ID_ANY)
		self.panel3 = wx.Panel(self.tabs, wx.ID_ANY)
		self.testpanel= wx.Panel(self.tabs, wx.ID_ANY)

		self.tabs.AddPage(self.cardpanel,"Learning")
		self.tabs.AddPage(self.panel3,"Reading")
		self.tabs.AddPage(self.testpanel,"Testing")
		self.tabs.AddPage(self.panel2,"Pie")
		
		self.shown = 0
		self.do_these = []

		print "Building out."
		self.buildTestPanel()
		self.buildReadingPanel()
		self.drawPie()
		self.buildCardForm()
		self.Refresh()
		self.cardpanel.Refresh()
		
		print "Finished creating manager window."

	def dothese(self,direction=False):
		if direction is False:
			direction = self.sessiondirection
		do_these = list(self.cardsession.todo[direction])
		if set(do_these) != set(self.do_these):
			random.shuffle(do_these)
			self.do_these = do_these
		return self.do_these

	def buildCardForm(self,session=0,dothese=[],is_practice=False,is_oldcheck=False,direction=1):
		self.dead = False
		self.cardlanguage = self.cardvocab.language
		self.carduser = self.cardvocab.user
		self.sessiondirection = direction
		self.cardsession = session
		if session == 0:
			self.cardsession = self.cardvocab.session
		if not (self.cardsession.todo[1]|self.cardsession.todo[-1]):
			print "Dead session: "+str(len(self.cardsession.todo[1])),str(len(self.cardsession.todo[-1])),str(len(self.cardvocab.words))
			self.dead = True
		else:
			dothese = self.dothese()
			if not dothese:
				if direction == 1:
					direction = -1
					dothese = self.dothese(direction)
				if not dothese:
					print "Undead session.",str(direction)
					self.dead = True
		self.dothese_saved = False
		self.is_practice = is_practice
		self.is_oldcheck = is_oldcheck
		self.cardform_dead = False
		self.direction = direction # 1 = forward, -1=back -- current direction of card
		try:
			self.cardvocab.current_word = dothese[0]
		except IndexError:
			self.cardvocab.current_word = pie.Word()
			self.do_these = [self.cardvocab.current_word]
			self.exemplify()
		if self.direction == 1:
			self.current_text = self.cardvocab.current_word.mainform
		else:
			self.current_text = self.cardvocab.current_word.gloss
		self.countstring = "Word %s of %s, direction: %s" 
		self.countstring2 = self.countstring % (str(self.do_these.index(self.cardvocab.current_word)+1),str(len(self.do_these)),direction)
		self.starline = self.cardvocab.current_word.getstars()
		self.SetStatusText(self.countstring2+"\t"+self.starline)
		self.exemplify()
		
# corner pie
		self.cornerpie = PiePanel(self.cardpanel,explode=(0.1,0.1,0.1,0.1,0.1,0.1),fracs=[1,1,1,1,1,1],labels=None,size=wx.Size(150,100),style=wx.EXPAND,figsize=(1,1),dpi=80, colors=('b', 'g', 'r', 'c', 'm', 'y'))
		self.cornerpie.SetBackgroundColour(self.color)

# dashboard controls
		width=self.cardpanel.GetClientSizeTuple()[0]
		self.dashbox=wx.StaticBox(self.cardpanel,size=(100,width))
		self.practiceoption = wx.RadioButton(self.cardpanel, label="Practice mode", style=wx.RB_GROUP)
		self.realoption = wx.RadioButton(self.cardpanel, label="Daily checkup")
		self.reviewoption = wx.RadioButton(self.cardpanel, label="Review old words.")
		self.practiceoption.SetValue(self.cardsession.is_practice)
		self.realoption.Bind(wx.EVT_RADIOBUTTON, self.onClickReal)
		self.practiceoption.Bind(wx.EVT_RADIOBUTTON, self.onClickPractice)
		self.reviewoption.Disable()
		self.newonlycheck = wx.CheckBox(self.cardpanel, label="New words only")
		self.newonlycheck.Bind(wx.EVT_CHECKBOX, self.onCheckNew)
		self.practicestring0="Practiced %s / %s new words" 
		self.practicetext0=wx.StaticText(self.cardpanel, label=self.practicestring0 % (
			str(len(self.cardvocab.session.practiced.intersection(self.cardvocab.words).intersection(self.cardvocab.session.newbies))), 
			str(len(set(self.cardvocab.words).intersection(self.cardvocab.session.newbies)))
			), size=wx.Size(200,30))
		self.pracresetbutton=wx.Button(self.cardpanel,id=wx.ID_ANY, label="&Reset\npractice",name="Reset")
		self.pracresetbutton.Bind(wx.EVT_BUTTON,self.onButton)
		self.pracresetbutton.SetToolTip(wx.ToolTip('Start practice again from the beginning.'))

# progress indicators
		self.stage1string="Tested %s / %s words forward"
		self.stage2string="Tested %s / %s words in reverse"
		self.stage1 = wx.StaticText(self.cardpanel, label=self.stage1string % (str(self.getTotalDone(1)),str(len(self.cardvocab.words))),size=wx.Size(200,30))
		self.stage2 = wx.StaticText(self.cardpanel, label=self.stage2string % (str(self.getTotalDone(-1)),str(self.cardvocab.session.reverse_total)),size=wx.Size(200,30))
		self.practicegauge = wx.Gauge(self.cardpanel, wx.ID_ANY, 100, size=(200,20))
		self.gauger1 = wx.Gauge(self.cardpanel, wx.ID_ANY, 100, size=(200, 20))
		self.gauger2 = wx.Gauge(self.cardpanel, wx.ID_ANY, 100, size=(200, 20))
		self.practicemeter1 = wx.Slider(self.cardpanel, value=0, minValue=0, maxValue=9, style=wx.SL_VERTICAL)
		self.practicemeter2 = wx.Slider(self.cardpanel, value=0, minValue=0, maxValue=9, style=wx.SL_VERTICAL)
		self.practicemeter1.Disable() # may eventually want to use this for in-session navigation
		self.practicemeter2.Disable()

#button setup
		self.wordbutton = wx.Button(self.cardpanel, label=self.current_text, style=wx.EXPAND,size=wx.Size(350,125),name="flip")
		self.ybutton = wx.Button(self.cardpanel, id=wx.ID_YES, name="yes")
		self.nbutton = wx.Button(self.cardpanel, id=wx.ID_NO, name="no", style=wx.EXPAND, size=wx.Size(250,20))
		self.gotbutton=wx.Button(self.cardpanel, label="&Rock solid", name="Done")
		self.sbutton = wx.Button(self.cardpanel, id=wx.ID_FORWARD, name="skip")
		self.obutton = wx.Button(self.cardpanel, id=wx.ID_BACKWARD, name="oops")
		self.obutton.Disable() # until first update()
		self.dbutton = wx.Button(self.cardpanel, label="Show/hide \n&details", name="details")
		self.rbutton = wx.Button(self.cardpanel, label="&Confusing", name="remove")

		self.ybutton.SetToolTip(wx.ToolTip("I know it."))
		self.nbutton.SetToolTip(wx.ToolTip("I don't know it."))
		self.dbutton.SetToolTip(wx.ToolTip("Show the examples and phonetic form."))
		self.sbutton.SetToolTip(wx.ToolTip("Go to next card, and come back later."))
		self.obutton.SetToolTip(wx.ToolTip("Undo your last action and go back to previous card."))
		self.rbutton.SetToolTip(wx.ToolTip("Get rid of this for now, learn it later."))
		self.gotbutton.SetToolTip(wx.ToolTip("I am 100% confident that I know and will not forget this word."))

		for button in [self.ybutton,self.nbutton,self.dbutton,
		#self.qbutton,
		self.sbutton,self.obutton,self.rbutton,self.gotbutton,self.wordbutton]:
			button.Bind(wx.EVT_BUTTON,self.onCardButton)
		self.wordbuttons=[self.ybutton,self.nbutton,self.gotbutton,self.sbutton,self.dbutton,self.rbutton]
		
# abc controls
		self.labelstring="You are in the process of learning %s words of %s. You have an estimated %s vocabulary, including words in all stages of learning, of %s words. \r\nYour current learning day began %s hours ago."
		self.atext = wx.TextCtrl(self.cardpanel, value=self.labelstring % (str(self.cardvocab.activecount),self.language,self.language,str(len([x for x in self.cardvocab.allwords if x.history])),str(round((time.time()-self.cardvocab.session.id)/3600,1))),style=wx.TE_READONLY|wx.TE_MULTILINE|wx.BORDER_NONE|wx.TE_NO_VSCROLL,size=wx.Size(300,50))
		self.atext.SetBackgroundColour(self.color)
		self.btext = wx.TextCtrl(self.cardpanel, style=wx.EXPAND|wx.TE_READONLY|wx.ALIGN_CENTER|wx.TE_MULTILINE|wx.BORDER_NONE|wx.TE_NO_VSCROLL,size=wx.Size(300,50))
		self.btext.SetFont(self.examplefont)
		self.btext.SetBackgroundColour(self.color)
		self.ctext = HtmlWin(self.cardpanel)
		self.cstring=u'<HTML>\n<BODY>\n%s</BODY>\n</HTML>'
		if self.cardvocab.language=="Korean":
			self.ctext.SetFonts("Gulim","Gulim") # necessary for rendering
		try:
			self.cstring=self.cstring.encode("utf-8","ignore")
		except UnicodeDecodeError:
			pass
		self.ctext.SetBackgroundColour(self.color)
		self.ctext.SetSize(wx.Size(300,125))

# notes panel
		self.notebar = HtmlWin(self.cardpanel)
		self.notestring = u'<HTML>\n<BODY>\n%s</BODY>\n</HTML>'
		self.notebar.SetBackgroundColour(self.color)
		self.notebar.SetSize(wx.Size(300,125))
		self.notebar.SetLabel(self.notestring % "")
		
# top menu
		menuBar = wx.MenuBar()
		self.filemenu = wx.Menu()
		self.filemenu.Append(99,  "&New day", "Load new vocabulary words") 
		self.filemenu.Append(100, "Toggle &practice mode", "Switch in or out of practice mode")
		self.filemenu.Append(101, "&Save\tCtrl+S", "Save current state of vocabulary")
		self.filemenu.Append(102, "&Open", "Open a different vocabulary")
		self.filemenu.Append(104, "Save &as", "Save current state of vocabulary")
		self.filemenu.Append(105, "&Create new", "Create a new course")
		self.Bind(wx.EVT_MENU,self.onNewDay,id=99)
		self.Bind(wx.EVT_MENU,self.onSave,id=101)
		self.Bind(wx.EVT_MENU,self.onOpenFile,id=102)
		# todo: 104, 100
		self.Bind(wx.EVT_MENU,self.onCreateNew,id=105)
		menuBar.Append(self.filemenu, "&File")

		self.editmenu = wx.Menu()
		self.editmenu.Append(199, "&Edit card\tCtrl+E", "Edit just the information for the current card.")
		self.editmenu.Append(200, "Edit &vocabulary", "Edit complete vocabulary")
		self.editmenu.Append(201, "&Settings","Edit settings")
		self.Bind(wx.EVT_MENU, self.onEditCard,id=199)
		self.Bind(wx.EVT_MENU, self.onEditSettings, id=201)
		menuBar.Append(self.editmenu, "&Edit")
		
		self.navmenu = wx.Menu()
		self.navmenu.Append(299, "&Next card\tCtrl+Right")
		self.navmenu.Append(300, "&Previous card\tCtrl+Left")
		self.Bind(wx.EVT_MENU,self.onCardForward,id=299)
		self.Bind(wx.EVT_MENU,self.onCardBack,id=300)
		menuBar.Append(self.navmenu, "&Navigation")
		
		self.helpmenu = wx.Menu()
		self.helpmenu.Append(399, "&About LanguagePie")
		self.Bind(wx.EVT_MENU, self.onAbout, id=399)
		menuBar.Append(self.helpmenu, "&Help")

		accel_tbl = wx.AcceleratorTable([
									(wx.ACCEL_CTRL, ord('E'), 199),
									(wx.ACCEL_CTRL, ord('S'), 101),
									(wx.ACCEL_CTRL, wx.WXK_WINDOWS_RIGHT, 299),
									(wx.ACCEL_CTRL, wx.WXK_WINDOWS_LEFT, 300),
								])
		self.SetAcceleratorTable(accel_tbl)
		self.SetMenuBar(menuBar)

# sizer setup
		self.mainsizer=wx.BoxSizer(wx.VERTICAL)
		toprow=wx.BoxSizer(wx.HORIZONTAL)
		toprow.Add(self.atext,flag=wx.EXPAND)
		toprow.Add((200,50),1)
		toprow.Add(self.cornerpie)
		self.mainsizer.Add(toprow,flag=wx.EXPAND)

		dashboardsizer=wx.StaticBoxSizer(self.dashbox,wx.HORIZONTAL)
		dashboardsizer_vertical=wx.BoxSizer(wx.VERTICAL)
		dashboardsizer_h2=wx.BoxSizer(wx.HORIZONTAL)
		dashboardsizer_h2.Add(self.realoption)
		dashboardsizer_h2.Add(self.practiceoption)
		dashboardsizer_h2.Add((50,10),1)
		dashboardsizer_h2.Add(self.newonlycheck)
		dashboardsizer_vertical.Add((10,10),1)
		dashboardsizer_vertical.Add(dashboardsizer_h2)

		dashboard_h3=wx.BoxSizer(wx.HORIZONTAL)
		dashboard_h3.Add(self.pracresetbutton)
		dashboardsizer_vertical.Add((10,10),1)
		dashboardsizer_vertical.Add(dashboard_h3)
		
		dashboard_h4=wx.BoxSizer(wx.HORIZONTAL)
		dashboard_h4.Add(self.reviewoption)
		dashboard_h4.Add((50,10),1)
		dashboardsizer_vertical.Add(dashboard_h4)
		dashboardsizer.Add(dashboardsizer_vertical)

		gaugelabelsizer=wx.BoxSizer(wx.VERTICAL)
		gaugesizer=wx.BoxSizer(wx.VERTICAL)
		gaugelabelsizer.Add(self.practicetext0)
		gaugelabelsizer.Add(self.stage1)
		gaugelabelsizer.Add(self.stage2)	
		gaugesizer.Add(self.practicegauge)
		gaugesizer.Add((10,10))
		gaugesizer.Add(self.gauger1)
		gaugesizer.Add((10,10))
		gaugesizer.Add(self.gauger2)
		dashboardsizer.Add((50,50),1)
		dashboardsizer.Add(gaugelabelsizer)
		dashboardsizer.Add(gaugesizer)
		self.mainsizer.Add(dashboardsizer)
		self.mainsizer.Add((50,50),1,flag=wx.EXPAND)

		mainrow=wx.BoxSizer(wx.HORIZONTAL)
		leftcolumn=wx.BoxSizer(wx.VERTICAL)
		leftcolumn.Add((25,25))
		leftcolumn.Add(self.dbutton)
		mainrow.Add(leftcolumn)
		mainrow.Add((50,50),1)

		midcolumn=wx.BoxSizer(wx.VERTICAL)
		aboveword=wx.BoxSizer(wx.HORIZONTAL)
		aboveword.Add(self.sbutton,flag=wx.ALIGN_LEFT)
		aboveword.Add((175,20),1)
		aboveword.Add(self.obutton)
		midcolumn.Add(aboveword)
		midcolumn.Add(self.wordbutton)
		belowmain=wx.BoxSizer(wx.HORIZONTAL)
		belowmain.Add(self.ybutton,flag=wx.ALIGN_LEFT)
		belowmain.Add((20,20))
		belowmain.Add(self.nbutton,flag=wx.EXPAND)
		midcolumn.Add(belowmain)
		mainrow.Add(midcolumn,flag=wx.ALIGN_CENTER)

		rightcolumn=wx.BoxSizer(wx.VERTICAL)
		rightcolumn.Add(self.rbutton,flag=wx.ALIGN_TOP)
		rightcolumn.Add((75,75),1)
		rightcolumn.Add(self.gotbutton)
		mainrow.Add((50,50),1)
		mainrow.Add(rightcolumn)

		mainrow.Add((50,50))
		mainrow.Add(self.practicemeter1)
		mainrow.Add(self.practicemeter2)
		self.mainsizer.Add(mainrow, flag=wx.ALIGN_CENTER)

		detailrow1 = wx.BoxSizer(wx.HORIZONTAL)
		detailrow1.Add(self.btext)
		self.mainsizer.Add(detailrow1)
		self.mainsizer.Add((50,50))

		detailrow2 = wx.BoxSizer(wx.HORIZONTAL)
		detailrow2.Add(self.ctext)
		detailrow2.Add((50,50),1)
		detailrow2.Add(self.notebar)
		self.mainsizer.Add(detailrow2)
		self.mainsizer.Add((50,50),1)
		
		self.setupPractice() # since we're starting in practice mode, have to make sure practice session is loaded.
		self.mainsizer.Layout()
		self.cardpanel.SetSizer(self.mainsizer)
		self.cardpanel.SetAutoLayout(True)
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.reviewoption.Hide()
		
	def onCheckNew(self,event):
		is_checked = self.newonlycheck.GetValue()
		if self.is_practice and is_checked:
			self.setupPractice(newonly=True)
	
	def onCreateNew(self,event):
		pass
	
	def getTotalDone(self,direction=1):
		try:
			thelist = self.cardvocab.session.getdone(direction)
		except AttributeError:
			if direction == 1:
				thelist = self.cardvocab.session.forward_successes | self.cardvocab.session.forward_failures
			else:
				thelist = self.cardvocab.session.reverse_successes | self.cardvocab.session.reverse_failures
			thelist = thelist.intersection(set(self.cardvocab.words))
#		try:
#			quickfound = thelist.intersection(set(self.cardvocab.quickfind.keys()))
#		except KeyError:
#		return len(quickfound)
		return len(thelist)
	
	def onClickReal(self,event):
		self.newonlycheck.SetValue(False)
		self.cardvocab.session.is_practice = False
		self.is_practice = False
		self.cardvocab.session.todo[1] = set(self.cardvocab.words) - (self.cardvocab.session.forward_successes | self.cardvocab.session.forward_failures)
		self.sessiondirection = 1
		self.dothese()
#		if len(self.cardvocab.session.todo[1]) < 2:
#			print "Nothing to do [1]!"
#			self.sessiondirection = -1
#		else:
#			print "Something to do!"
#			self.sessiondirection = 1
#		self.resetCardForm(dothese=self.do_these)
		self.resetCardForm(dothese=self.cardvocab.session.todo[self.sessiondirection])
		
	def onClickPractice(self,event):
			print "Clicked to practice mode."
			dia = wx.MessageDialog(self, "Give up current test and return to practice mode?", "Confirm Switchback", wx.OK|wx.CANCEL|wx.ICON_QUESTION)
			if dia.ShowModal() == wx.ID_CANCEL:
				dia.Destroy()
				self.realoption.SetValue(True)
				return False
			else:
				dia.Destroy()
				self.setupPractice()
				print "Practice set up."
				return True
	
	def onAbout(self,event):
		from wx.lib.wordwrap import wordwrap
		info = wx.AboutDialogInfo()
		info.Name = "LanguagePie"
		info.Version = "0.0.1 Alpha"
		info.Copyright = "(C) 2011 Calumet Language Services"
		info.Description = wordwrap(
			"Information goes here. ",
			350, wx.ClientDC(self.cardpanel))
		info.WebSite = ("http://www.languagepie.com", "LanguagePie.com")
		wx.AboutBox(info)
	
	def setupPractice(self,newonly=False):
		chunksize = self.cardvocab.user.chunksize
		if newonly is False:
			newonly = bool(self.newonlycheck.GetValue())
		practicees = self.cardvocab.session.practiced
		chunk = list(set(self.cardvocab.words)-practicees)
		print len(chunk), len(practicees)
		random.shuffle(chunk)
		if newonly:
			chunk = [x for x in chunk if len(x.successes)==0]
		if len(chunk) == 0:
			self.wordbutton.SetLabel("the end.")
			return
		chunk = chunk[:chunksize]
		if chunk:
			random.shuffle(chunk)
			print "Chunk size: ", str(len(chunk))
			practicesession = pie.Session(self.cardvocab,is_practice=True)
			practicesession.todo[1] = set(chunk)
			self.is_practice = True
			self.direction = 1
			self.sessiondirection = 1
			self.resetCardForm(session=practicesession,is_practice=True,dothese=chunk)
	
	def onSave(self,event=False):
			this=threading.Thread(target=self.onSave_launch) #saving a large vocab can slow things down a lot.
			this.start()
	
	def onSave_launch(self):
		print "Launching save thread..."
		time.sleep(1) # experimental
		meh = self.cardvocab.save()
		print "File saved successfully."
		
	def onEditCard(self,event):
		self.editform = CardEditForm(self,self.cardvocab,self.cardvocab.current_word,self.do_these)
		self.editform.Show()
		
	def onEditSettings(self,event):
		self.settingsform = SettingsForm(self,self.cardvocab)
		self.settingsform.Show()

	def exemplify(self,direction=1):
			self.card_examples = dict([(x,x.phonetic) for x in self.do_these]) # will display phonetic form on request, just below main form
			self.card_examples2 = {}
			self.card_examples3 = {}
			for v in self.do_these:
				self.card_examples2[v] = "\n".join(u'<P>%s <A href="%s">\u2197</A></P>\n<P></P>\n<P></P>' % (x.text,x.href.decode("utf-8","ignore")) for x in v.examples)
				self.card_examples3[v] = "\n".join('<P>%s \n</P>' % (x.clue) for x in v.examples)
		
	def onNewDay(self,event):
		daysworth = self.cardvocab.user.perdiem # currently entered #words to get for new day
		self.cardvocab.newsession(daysworth=daysworth)
		print "Loaded new session; exemplifying..."
		self.exemplify()
		print "Exemplified, setting up practice..."
		self.setupPractice()
#		self.onSave()
		
	def onOpenFile(self,event):
		dialog = wx.FileDialog (self.cardpanel, message = 'Open vocabulary file', wildcard = "Text files (*.txt)|*.txt", style = wx.OPEN )
		if dialog.ShowModal() == wx.ID_OK:
			selected = dialog.GetPath()
			self.loadFile(selected)
		dialog.Destroy()

	def resetCardForm(self,vocab=False,session=False,dothese=[],is_practice=False,is_oldcheck=False):
# clean up defaults
		if vocab is not False:
			self.cardvocab = vocab
		if session is not False:
			self.cardsession = session
		elif is_practice is False: # reset
			self.cardsession = self.cardvocab.session
		if is_practice is False: # is this necessary?
			self.is_practice=bool(self.practiceoption.GetValue())
			print "Is practice: "+str(self.is_practice)
		else:
			self.practiceoption.SetValue(True)
		self.cardvocab.cardsession = self.cardsession
		if self.is_practice and self.cardsession == self.cardvocab.session:
			self.cardsession = pie.Session(self.cardvocab,is_practice=True)
			if self.cardsession.id == self.cardvocab.session.id: 
				self.cardsession.id += 1
			self.cardvocab.cardsession = self.cardsession
		if dothese:
			self.do_these = list(dothese)
			random.shuffle(self.do_these)
			print "Len dothese: ",str(len(self.do_these))
		self.exemplify()
		try:
			self.cardvocab.current_word = self.do_these[0]
		except IndexError:
			print "Creating blank word."
			self.cardvocab.current_word = pie.Word()
			self.do_these = [pie.Word()]
			self.exemplify()
		if self.sessiondirection == 1:
			self.current_text=self.cardvocab.current_word.mainform
		elif self.sessiondirection == -1:
			self.current_text=self.cardvocab.current_word.gloss
		self.wordbutton.SetLabel(self.current_text)
		self.setTextSize(self.wordbutton,8)
		self.atext.SetLabel(self.labelstring % (str(self.cardvocab.activecount),self.cardvocab.language,self.cardvocab.language,str(len([x for x in self.cardvocab.allwords if x.history])),str(round((time.time()-self.cardvocab.session.id)/3600,1))))
		if self.sessiondirection==1:
			self.btext.SetLabel(self.card_examples[self.cardvocab.current_word])
			self.ctext.SetPage(self.cstring % self.card_examples2[self.cardvocab.current_word])
		elif self.sessiondirection==-1:
			self.btext.SetLabel(self.cardvocab.current_word.glossed)
			self.ctext.SetPage(self.cstring % self.card_examples3[self.cardvocab.current_word])
		for p in [self.practicemeter1, self.practicemeter2]:
			p.Show(self.is_practice)
			p.SetValue(0)

# display of current-session info
		self.update_count()
		self.starline = self.cardvocab.current_word.getstars()
		self.updatePie()
		self.update()
		print "Len dothese: ",str(len(self.do_these))

	def update_count(self):
		directions = {1:"forward",-1:"reverse"}
		direction = directions[self.sessiondirection]
		if self.cardsession.redoing:
				direction += " (redo)"
		try:
			self.countstring2 = self.countstring % (str(self.do_these.index(self.cardvocab.current_word)+1),str(len(self.do_these)),direction)
		except:
			print str(self.cardvocab.current_word),str(len(self.do_these)),direction
			self.countstring2 = ""

	def buildReadingPanel(self):
		panel = self.panel3
		self.notloaded = True
		self.lastcheck = time.time()
		self.clipcheck = False
		self.activereading = pie.Reading(language=self.cardvocab.language,analysis=False)
		topstring = "This is your space for collecting texts that you want to read, or that you want to target for learning."
		self.currentclip = ""
		self.Bind(wx.EVT_IDLE, self.checkClipBoard)

		toptext = wx.StaticText(panel,label=topstring)
		toptext.SetBackgroundColour(self.color)
		self.checkit = wx.CheckBox(panel,0, "Use as pasteboard")
		self.checkit.Bind(wx.EVT_CHECKBOX,self.updatePasteAction)
		self.analysis_checkbox = wx.CheckBox(panel, label="Enable analysis")
		self.analysis_checkbox.Bind(wx.EVT_CHECKBOX,self.onEnableAnalysis)
		self.bigbox = wx.TextCtrl(panel,size=wx.Size(400,300),style=wx.TE_MULTILINE)
		self.bigbox.Bind(wx.EVT_TEXT,self.onReadingEdit)
		self.bigboxbutton = wx.Button(
			panel,
			id=wx.ID_SAVE,
			label="&Analyze and save",
			size=wx.Size(150,20)
			)
		self.bigboxbutton.Bind(wx.EVT_BUTTON,self.onSaveReading)
		self.bigboxbutton2 = wx.Button(
			panel, 
			id=wx.ID_ANY, 
			label="&Save without analyzing", 
			size=wx.Size(150,20)
			)
		self.bigboxbutton2.Bind(wx.EVT_BUTTON,self.saveCurrentReading)
		self.titletext = wx.StaticText(panel,label="Title: ")
		self.titlebox = wx.TextCtrl(panel,size=wx.Size(400,20))
		self.titlebox.Bind(wx.EVT_TEXT,self.onReadingEdit)
		self.urltext = wx.StaticText(panel,label="Location (such as URL): ")
		self.urlbox = wx.TextCtrl(panel,size=wx.Size(350,20))
		self.urlbox.Bind(wx.EVT_TEXT,self.onReadingEdit)
		self.progressor = wx.Gauge(panel)
		
		self.reading_toptext = wx.StaticText(panel,label=
		"You have %s readings in your library.\nClick the radio button next to a reading to edit or view it." 
		% str(len(self.cardvocab.readings)))
		self.reading_box = wx.StaticBox(panel)
		self.reading_list = {}
		for r in self.cardvocab.readings:
			try:
				reading_xml = open(os.path.join(workingdir,str(r))).read()
			except:
				print "Unable to load "+str(r)
				continue
			reading = pie.Reading()
			reading.load(reading_xml)
			newbox = wx.RadioButton(panel, label=reading.title, style=wx.RB_GROUP)
			newbox.Bind(wx.EVT_RADIOBUTTON,self.onLoadReading,id=r)
			self.reading_list[reading]=newbox

		leftsizer = wx.BoxSizer(wx.VERTICAL)
		leftsizer.Add(toptext)
		leftsizer.Add(self.checkit)
		titlesizer = wx.BoxSizer(wx.HORIZONTAL)
		titlesizer.Add(self.titletext)
		titlesizer.Add(self.titlebox)
		leftsizer.Add(titlesizer)
		urlsizer = wx.BoxSizer(wx.HORIZONTAL)
		urlsizer.Add(self.urltext)
		urlsizer.Add(self.urlbox)
		leftsizer.Add(urlsizer)
		leftsizer.Add(self.bigbox)
		leftsizer.Add(self.bigboxbutton)
		leftsizer.Add(self.bigboxbutton2)
		leftsizer.Add(self.analysis_checkbox)
		leftsizer.Add(self.progressor)
		
		rightsizer = wx.BoxSizer(wx.VERTICAL)
		sorted_readings = [(x.lastupdate,x) for x in self.reading_list.keys()]
		sorted_readings.sort()
		sorted_readings.reverse()
		rightsizer.Add(self.reading_toptext)
		rightsizer.Add(self.reading_box)
		for s in sorted_readings:
			rightsizer.Add(self.reading_list[s[1]])

		mainsizer=wx.BoxSizer(wx.HORIZONTAL)
		mainsizer.Add(leftsizer)
		mainsizer.Add((50,50),1)
		mainsizer.Add(rightsizer)
		mainsizer.Layout()
		panel.SetSizer(mainsizer)
		panel.SetAutoLayout(True)
		self.progressor.Hide()
		
	def updatePasteAction(self,event):
		self.clipcheck=self.checkit.GetValue()
		if self.clipcheck: # Don't paste what is in the clipboard at the moment the box is ticked.
			wx.TheClipboard.Open()
			do=wx.TextDataObject()
			success=wx.TheClipboard.GetData(do)
			wx.TheClipboard.Close()
			self.currentclip=do.GetText()
		else:
			self.currentclip=""
			
	def onSaveReading(self,event=False):
		this=threading.Thread(target=self.saveCurrentReading,args=(True,True))
		this.start()
		
	def saveCurrentReading(self,event=False,analyze=False):
		self.activereading.lastupdate = int(time.time())
		if analyze is not False:
			self.bigboxbutton.SetLabel("Saving...")
			self.progressor.Show()
			self.activereading.text=self.bigbox.GetValue()
			self.activereading.process(callme=self.updateReadingGauge,param=True) # create frequency 
		if self.activereading.id not in self.cardvocab.readings:
			self.cardvocab.readings.append(self.activereading.id)
		dump = self.activereading.dump()
		file = open(os.path.join(workingdir,str(self.activereading.id)),"w")
		with file:
			file.write(dump)
		self.bigboxbutton.SetLabel("&Analyze and save")

	def onReadingEdit(self,event):
		pass
	
	def onEnableAnalysis(self,event):
		if self.analysis_checkbox.GetValue():
			try:
				foo=pie.lib
			except AttributeError:
				self.activereading.enable_analysis()
		else:
			self.bigboxbutton.Disable()
	
	def onLoadReading(self,event):
		readingid=event.GetId()
		ids = dict([(x.id,x) for x in self.cardvocab.readings])
		try:
			reading = ids[readingid]
		except KeyError:
			print "ID not in readings: "+str(readingid)
			return False
		self.bigbox.SetValue(reading.text)
		self.titlebox.SetValue(reading.title)
		self.urlbox.SetValue(reading.location)
		return True
		
	def updateReadingGauge(self,value=False,total=100):
		if type(value)==dict:
			total=0
			thisval=0
			for v in value.keys():
				total += value[v]
				if v in self.cardvocab.quickfind.keys():
					if self.cardvocab.quickfind[v] in set(self.cardvocab.words)|self.cardvocab.done:
						thisval += value[v]
			print thisval,total
			value = thisval
		elif value is False:
			value = len(self.cardvocab.readings)
		outval = 100.0*float(value)/float(total)
		outval = int(outval)
		self.progressor.SetValue(outval)
	
	def checkClipBoard(self,event):
		if self.notloaded:
			if not self.analysis_checkbox.GetValue():
				try:  # see if language-specific library has loaded.
					fubar=pie.lib.frequentize
				except (AttributeError, NameError):
					self.bigboxbutton.SetLabel("Loading language data...")
					self.bigboxbutton.Disable()
				else:
					self.notloaded=False
					self.bigboxbutton.SetLabel("&Analyze and save")
					self.bigboxbutton.Enable()
		if time.time()-self.lastcheck < 0.5:
			return
		elif not self.clipcheck:
			return
#		if not wx.TheClipboard.IsOpened(): # does not work, always returns True
		wx.TheClipboard.Open()
		do = wx.TextDataObject()
		success = wx.TheClipboard.GetData(do)
		wx.TheClipboard.Close()
		if not success:
			return
		newval=do.GetText()
		if self.currentclip == newval:
			return
		self.currentclip=newval
		self.bigbox.SetValue(self.bigbox.GetValue()+"\n\n"+newval)

	def onCardButton(self, event):
		button = event.GetEventObject()
		response = button.GetName()[:1]
		starttime = time.time()
		print "card",response
		if response == "y":
			self.ybutton.Disable()
			self.nbutton.Disable()
			if self.is_practice:
				print "adding to practiced"
				self.cardvocab.session.practiced.add(self.cardvocab.current_word)
			self.cardvocab.current_word.succeed(sessionid=self.cardsession.id,
				is_practice=self.is_practice, direction=self.sessiondirection,
				vocab=self.cardvocab, session=self.cardsession, is_final=bool(len(self.cardvocab.current_word.successes) >= 8))
			try: 
				self.cardsession.redo.remove(self.cardvocab.current_word) # avoid double-dipping if a card has been skipped but then returned to
			except KeyError:
				pass
		elif response == "n":
			self.ybutton.Disable()
			self.nbutton.Disable()
			self.cardvocab.current_word.fail(self.cardsession.id,self.is_practice,self.sessiondirection,vocab=self.cardvocab,session=self.cardsession)
			if self.is_practice:
				self.cardsession.redo.add((self.sessiondirection,self.cardvocab.current_word)) # for practice session, repeat until done
				self.cardvocab.session.practiced.add(self.cardvocab.current_word)
			if self.is_oldcheck:
				self.parent.wordboxes[self.cardvocab.current_word]=False
		elif response == "s":#skip
			self.onCardForward()
		elif response == "o": # oops  
			self.onCardBack()
			return #don't advance
		elif response == "q": # quit and save
			if not self.is_practice:
				self.closeout()
			else:
				self.OnClose()
			return
		elif response == "f": #flip
			label=self.wordbutton.GetLabel().strip()
			if label == "" or label == "Click here to begin":
				print "empty card, loading dothese."
				self.sessiondirection = 1
				if self.do_these:
					print str(len(self.do_these))
					self.resetCardForm(dothese=self.do_these) # was self.cardvocab.session.todo[1]
				else:
					print "new session."
					self.cardvocab.newsession()
					self.resetCardForm(dothese=self.cardvocab.session.todo[1])
			elif label.startswith("the end.") and self.is_practice:
				print "Proceeding to next chunk."
				self.onButton(response="N") # spaghetti warning
			else:
				print "Flipping..."
				self.flip()
				self.nbutton.SetFocus()
			return
		elif response == "d": #details toggle
			self.showhide()
			self.nbutton.SetFocus()
			return
		elif response == "r": #remove
			index = self.do_these.index(self.cardvocab.current_word)
			print "removing ..." + str(index)
			self.cardvocab.sequester(self.cardvocab.current_word)
			try:
				self.cardvocab.words.remove(self.cardvocab.current_word)
			except:
				print "Unable to remove "+self.cardvocab.current_word.rom+" from cardvocab"
			self.do_these.remove(self.cardvocab.current_word)
			self.cardsession.todo[self.sessiondirection].remove(self.cardvocab.current_word)
			print len(self.do_these)
			if not self.do_these: # only one word in the set?
				self.onend()
			if index == len(self.do_these): 
				index -= 1
			self.cardvocab.current_word = self.do_these[index]
			self.direction = self.sessiondirection
			self.update()
			return
		elif response == "D": #done with 
			self.solidify(self.cardvocab.current_word)
			return
		if response in ["y","n"]:
			if time.time() - starttime < 0.3: # maintain consistent delay
				time.sleep(0.3 - (time.time() - starttime))
		self.ybutton.Enable()
		self.nbutton.Enable()
		outcome = self.advance()
		self.direction = self.sessiondirection
		if outcome is not False: # avoid double update
			self.update()
		return True
		
	def OnClose(self,event=False):
		if event:
			print "triggered close event."
			dia = wx.MessageDialog(self, "If you exit now, all of your activity for this session will be lost. To go back and save your work, click 'Cancel'. ", "Confirm Exit", wx.OK|wx.CANCEL|wx.ICON_QUESTION)
			if dia.ShowModal() == wx.ID_CANCEL:
				dia.Destroy()
				return
			dia.Destroy()
		else: # "quit and save"
			print "Saving on close..."
			self.cardvocab.save()
		self.Destroy()
	
	def onCardForward(self,event=False):
		if event:
			print str(event)
		self.cardvocab.current_word.skip(session=self.cardsession,vocab=self.cardvocab,direction=self.sessiondirection)
		self.cardsession.redo.add((self.sessiondirection,self.cardvocab.current_word))

	def onCardBack(self,event=False): # currently smooshing undo and back together
		if not self.is_practice:
			foo=self.cardvocab.undo(session=self.cardsession,direction=self.sessiondirection)
		index=self.do_these.index(self.cardvocab.current_word)
		print index
		if index > 0:
			self.cardsession.todo[self.sessiondirection].add(self.cardvocab.current_word)
			self.cardvocab.current_word = self.do_these[index-1]
		self.update()

	def final_tidy(self):
		if self.cardsession.redoing: #done with current redo, put things back in order
			self.cardsession.redoing = False
			print "restoring words saved : ",str(len(self.cardvocab.words)),str(len(self.cardvocab.words_saved))
			self.cardvocab.words = self.cardvocab.words_saved
			self.do_these = self.dothese_saved
			self.cardvocab.words_saved = False
			self.dothese_saved = False
		if self.is_practice:
			self.cardvocab.current_word = self.cardvocab.words[0] #reset the ticker
	
	def advance(self):
		print "Advancing..."
		try: # proceed to next card
			self.cardvocab.current_word = self.do_these[self.do_these.index(self.cardvocab.current_word)+1]
			print self.do_these.index(self.cardvocab.current_word)
			if self.cardvocab.current_word not in self.cardsession.todo[self.sessiondirection]:
				print "Phantom!", self.cardvocab.current_word.rom
				self.cardvocab.current_word = self.do_these[self.do_these.index(self.cardvocab.current_word)+1]
		except IndexError:
			print "Reached end."
			self.onend()
			return False
		if self.sessiondirection == 1:
			self.current_text = self.cardvocab.current_word.mainform
			if self.is_practice and not self.cardsession.redoing:
				try:
					self.practicemeter1.SetValue(self.do_these.index(self.cardvocab.current_word))
				except Exception:
					print "Unable to set practicemeter1.", str(self.do_these.index(self.cardvocab.current_word))
		elif self.sessiondirection == -1:
			self.current_text = self.cardvocab.current_word.gloss
			if self.is_practice and not self.cardsession.redoing:
				try:
					self.practicemeter2.SetValue(self.do_these.index(self.cardvocab.current_word))
				except Exception:
					print "Unable to set practicemeter2.", str(self.do_these.index(self.cardvocab.current_word))

	def update(self,is_end=False): #update displays for new word
# this probably doesn't need to be triggered on every card-update
		self.exemplify()
		self.fliptime=time.time()
		self.wordbutton.SetFont(self.wordfont)
		if is_end:
			self.current_text="the end.\n click to continue..."
			self.wordbutton.SetFont(self.littlefont)
			self.cardvocab.current_word = pie.Word()
			self.do_these = [self.cardvocab.current_word]
			self.ybutton.Disable()
			self.nbutton.Disable()
#			self.shown = 0
			self.wordbutton.SetLabel(self.current_text)
		else:
			if self.sessiondirection == 1:
				self.current_text=self.cardvocab.current_word.mainform
			if self.sessiondirection == -1:
				self.current_text=self.cardvocab.current_word.gloss
			self.wordbutton.SetLabel(self.current_text)
			self.setTextSize(self.wordbutton,8)
		print "Updating card, #successes: "+self.cardvocab.current_word.rom.encode("utf-8","ignore"),len(self.cardvocab.current_word.successes)
		self.starline=self.cardvocab.current_word.getstars()
		cstring = self.cstring % ""
		if self.shown:
			if self.sessiondirection == 1:
				self.btext.SetLabel(self.card_examples[self.cardvocab.current_word])
				if self.cardvocab.current_word in self.card_examples2.keys():
					cstring = self.cstring % self.card_examples2[self.cardvocab.current_word]
				try:
					cstring = cstring.encode("utf-8","ignore")
				except UnicodeDecodeError:
					pass
			else:
				self.btext.SetLabel(self.cardvocab.current_word.glossed)
				cstring = self.cstring % self.card_examples3[self.cardvocab.current_word]

		else:
			self.btext.SetLabel("")
		self.ctext.SetPage(cstring)
		self.notebar.SetPage(self.notestring % "\n".join([str(x) for x in self.cardvocab.current_word.notes]))
		self.update_count()
		self.SetStatusText(self.countstring2+"\t"+self.starline+"\t"+str(self.cardvocab.current_word.tally)) # must follow update_count
		self.obutton.Enable(bool(self.do_these.index(self.cardvocab.current_word)>0))
		for b in self.wordbuttons: b.Enable(bool(not is_end))
		self.cardvocab.getstats()
		print "Refreshing manager window..."
		self.stage1.SetLabel(self.stage1string % (str(self.getTotalDone(1)),str(len(self.cardvocab.words))))
		self.stage2.SetLabel(self.stage2string % (str(self.getTotalDone(-1)),str(self.cardvocab.session.reverse_total)))
		praclabel=self.practicestring0 % (
			str(len(self.cardvocab.session.practiced.intersection(self.cardvocab.words).intersection(self.cardvocab.session.newbies))), 
			str(len(set(self.cardvocab.words).intersection(self.cardvocab.session.newbies)))
			)
		self.practicetext0.SetLabel(praclabel)
		self.setGauges()
		
	def solidify(self,word,update=True):
		index = self.do_these.index(self.cardvocab.current_word)
		print "Removing rock-solid word."
		word.succeed(sessionid=self.cardsession.id,vocab=self.cardvocab,session=self.cardsession,is_final=True)
		word.history.append((400,time.time(),self.cardsession.id))
		self.cardvocab.sequester(self.cardvocab.current_word,newstatus=-1)
		try:
			self.do_these.remove(word)
		except ValueError:
			pass
		if word == self.cardvocab.current_word:
			if index >= len(self.do_these): index-=1
			self.cardvocab.current_word = self.do_these[index]
		if update is not False:
			self.direction = self.sessiondirection
			self.update()

	def onend(self):
		if self.is_practice and self.sessiondirection == -1:
			self.cardvocab.session.practiced |= self.cardsession.forward_successes|self.cardsession.forward_failures
			print "len practiced: ",str(len(self.cardvocab.session.practiced)),str(len(self.cardvocab.words))
		if self.cardsession.redoing: #done with current redo, put things back in order
			print "restoring words saved"
			self.cardvocab.words = self.cardvocab.words_saved
			if self.dothese_saved is not False:
				self.do_these = self.dothese_saved
				self.dothese_saved = False
			self.cardvocab.words_saved = False
			self.cardsession.redoing = False
		if self.cardsession.redo:
			if self.cardvocab.words_saved is False: # avoid overwrite by multiple redoes
				self.cardvocab.words_saved = list(self.cardvocab.words)
				self.dothese_saved = list(self.do_these)
			print "Redo: "+str(len(self.cardvocab.words))
# now put things in order 
			self.cardsession.todo[self.sessiondirection] = set(x[1] for x in self.cardsession.redo)
			self.do_these = [x[1] for x in self.cardsession.redo]
			print self.sessiondirection,len(self.cardsession.todo[self.sessiondirection])
			self.cardsession.redo = set()
			self.cardsession.redoing = True
			if self.cardvocab.current_word == self.do_these[0]:
				self.do_these = self.do_these[1:]
				self.do_these.append(self.cardvocab.current_word)
			self.cardvocab.current_word = self.do_these[0]
			self.update()
		elif self.sessiondirection == 1: # reverse course ... 
			print "Reversing..."
			self.sessiondirection = -1
			self.direction = -1
			self.dothese()
			self.cardsession.reverse_total = len(self.cardsession.todo[-1])
			if self.do_these:
				if self.do_these[0] == self.cardvocab.current_word: # don't go straight to the same card.
					self.do_these.append(self.do_these[0])
					self.do_these = self.do_these[1:]
				self.cardvocab.current_word = self.do_these[0]
				self.current_text = self.do_these[0].gloss
				self.update()
			else:
				print "is end (2)."
				self.update(is_end=True)
				return
		else:
			print "is end."
			self.update(is_end=True)

	def closeout(self):
		dump=self.cardvocab.dump()
		if self.cardvocab.path:
			file=open(self.cardvocab.path,"w")
			with file:
				file.write(dump)
		self.OnClose()
			
	def setTextSize(self,obj,maxlen=10):
		obj.SetFont(self.wordfont)
		if len(obj.GetLabel()) > 8:
			print "reducing font."
			obj.SetFont(self.wordfont_small)

	def flip(self):
		label = self.wordbutton.GetLabel().strip()
		if self.cardvocab.current_word.mainform.strip() == self.cardvocab.current_word.gloss.strip():
			equalityproblem = True
		else:
			equalityproblem = False
		if label == self.cardvocab.current_word.mainform.strip() and not (equalityproblem and self.direction == -1):
				self.wordbutton.SetLabel(self.cardvocab.current_word.gloss)
				self.ctext.SetPage(self.cstring % self.card_examples3[self.cardvocab.current_word])
				if self.shown:
					self.btext.SetLabel(self.cardvocab.current_word.glossed) #long-form defn
				else:
					self.btext.SetLabel("")
		elif label == self.cardvocab.current_word.gloss.strip():
				self.wordbutton.SetLabel(self.cardvocab.current_word.mainform)
				if self.shown:
					self.btext.SetLabel(self.card_examples[self.cardvocab.current_word]) #long-form defn
					self.ctext.SetPage(self.cstring % self.card_examples2[self.cardvocab.current_word])
				else:
					self.btext.SetLabel("")
					self.ctext.SetPage(self.cstring % "")
		else: # something weird?
			print "Weird label on wordbutton."
			self.wordbutton.SetLabel(self.cardvocab.current_word.mainform)
			self.current_text = self.cardvocab.current_word.mainform
		self.setTextSize(self.wordbutton,8)
		self.direction = 0-self.direction

	def showhide(self):
		print "Shown, direction: "+str(self.shown),str(self.direction)
		self.shown=list(set([0,1])-set([self.shown]))[0]
		if not self.shown:
			self.btext.SetLabel("")
			self.ctext.SetPage(self.cstring % "")
		elif self.direction==1:
			self.btext.SetLabel(self.card_examples[self.cardvocab.current_word])
			self.ctext.SetPage(self.cstring % self.card_examples2[self.cardvocab.current_word])
		elif self.direction==-1:
			self.btext.SetLabel(self.cardvocab.current_word.glossed)
			self.ctext.SetPage(self.cstring % self.card_examples3[self.cardvocab.current_word])
		print self.shown
		
	def saveandclose(self,event):
		try:
			self.cardvocab.save()
		except:
			print "Unable to save."
		self.Destroy()
		
	def setGauges(self,event=False): #event is thrown away
		val1=100.0 * (
			float(
				len(
					self.cardvocab.session.forward_successes
				) + len(
					self.cardvocab.session.forward_failures
				)
			)
		) / float(
			self.cardvocab.activecount + int(self.cardvocab.activecount==0)
		)
		val2=100.0 * (
			float(
				len(
						self.cardvocab.session.reverse_successes
					) + len(
						self.cardvocab.session.reverse_failures
					)
				) / (
					float(
						len(
							self.cardvocab.session.forward_successes
						) + int(
							len(
								self.cardvocab.session.forward_successes
							) == 0
						)
					)
				)
			)
		activenew=len(set(self.cardvocab.words).intersection(self.cardvocab.session.newbies))
		val3=100.0 * (
			float(
				len(
					self.cardvocab.session.practiced.intersection(self.cardvocab.session.newbies)
					)
				) / (
						activenew + int(activenew==0)
					)
				)
		self.gauger1.SetValue(val1)
		self.gauger2.SetValue(val2)
		self.practicegauge.SetValue(val3)

		if val1 > 50.0:
			self.cornerpie.pielets[0][1].set_facecolor(self.color_floats)
		else:
			self.cornerpie.pielets[0][1].set_facecolor(self.cornerpie.colors[1])
		if val1 > 99.0:
			self.cornerpie.pielets[0][4].set_facecolor(self.color_floats)
		else:
			self.cornerpie.pielets[0][4].set_facecolor(self.cornerpie.colors[4])
		if val2 > 50.0:
			self.cornerpie.pielets[0][2].set_facecolor(self.color_floats)
		else:
			self.cornerpie.pielets[0][2].set_facecolor(self.cornerpie.colors[2])
		if val2 > 99.0:
			self.cornerpie.pielets[0][5].set_facecolor(self.color_floats)
		else:
			self.cornerpie.pielets[0][5].set_facecolor(self.cornerpie.colors[5])
		if val3 > 50.0: 
			self.cornerpie.pielets[0][0].set_facecolor(self.color_floats)
		else:
			self.cornerpie.pielets[0][0].set_facecolor(self.cornerpie.colors[0])
		if val3 > 99.0:
			self.cornerpie.pielets[0][3].set_facecolor(self.color_floats)
		else:
			self.cornerpie.pielets[0][3].set_facecolor(self.cornerpie.colors[3])
		self.cornerpie.draw()
		
		print str((val1,val2,val3))
		return (val1,val2,val3)

	def buildTestPanel(self): # note to future self: this code assumes no dynamic change in band size
		panel = self.testpanel
		self.testing = LevelTest(self.cardvocab,frame=self)
		self.testingstring = "Measured through level-testing, your current vocabulary size is estimated at approximately %s words with respect to a reference vocabulary of %s %s words.  Press the button to test your level now."
		self.testingtext = wx.StaticText(panel,label=self.testingstring % (str(self.cardvocab.user.testval),str(len(self.cardvocab.allwords)),str(self.cardvocab.language)),size=wx.Size(400,50),style=wx.EXPAND|wx.TE_READONLY|wx.BORDER_NONE|wx.TE_MULTILINE|wx.TE_NO_VSCROLL)
		self.resulttext = wx.StaticText(panel,label="",size=wx.Size(400,100))
		self.applybutton = wx.Button(panel, label="Mark all words in these bands as known.",style=wx.EXPAND)
		self.applybutton.Bind(wx.EVT_BUTTON,self.onTestApply)
		self.testingtext.SetBackgroundColour(self.color)
		self.resulttext.SetBackgroundColour(self.color)
		self.bandages = []
		for b in self.testing.bands:
			if len(b) < 10: continue
			bandsample = [x.mainform.encode("utf-8","ignore") for x in random.sample(b,3)]
			bandstring = "Band %s: %s words including %s, %s, %s ... " % (str(self.testing.bands.index(b)+1),len(b), bandsample[0], bandsample[1], bandsample[2])
			self.bandages.append(bandstring)
		self.bandbox = wx.CheckListBox(panel,choices=self.bandages,size=(400,80))
		self.bandbox.SetBackgroundColour(self.color)
		self.test_ybutton = wx.Button(panel, label="&Yes", name="yes")
		self.test_nbutton = wx.Button(panel, label="&No", name="no")
		self.test_wordbutton = wx.Button(panel, label="NEW TEST?", size=wx.Size(360,200),name="word")
		self.test_resetbutton = wx.Button(panel, label="Start\nover")
		self.test_wordbutton.SetFont(self.wordfont)
		self.test_resetbutton.Bind(wx.EVT_BUTTON, self.onTestReset)
		for button in [self.test_ybutton,self.test_nbutton,self.test_wordbutton]:
			button.Bind(wx.EVT_BUTTON, self.onTestClick)

		self.testsizer=wx.BoxSizer(wx.VERTICAL)
		toprow=wx.BoxSizer(wx.HORIZONTAL)
		midrow=wx.BoxSizer(wx.HORIZONTAL)
		midleft=wx.BoxSizer(wx.VERTICAL)
		midright=wx.BoxSizer(wx.VERTICAL)
		bottomup=wx.BoxSizer(wx.HORIZONTAL)
		bottomdown=wx.BoxSizer(wx.HORIZONTAL)
		toprow.Add(self.testingtext)
		toprow.Add(self.test_resetbutton)
		self.testsizer.Add(toprow,flag=wx.ALIGN_CENTER)
		self.testsizer.Add(self.bandbox,flag=wx.ALIGN_CENTER)
		self.testsizer.Add((50,50))
		midrow.Add(self.test_wordbutton,flag=wx.ALIGN_CENTER)
		self.testsizer.Add(midrow,flag=wx.ALIGN_CENTER)
		bottomup.Add(self.test_ybutton,flag=wx.ALIGN_LEFT)
		bottomup.Add((50,50),1,flag=wx.ALIGN_CENTER)
		bottomup.Add(self.test_nbutton,flag=wx.ALIGN_RIGHT)
		self.testsizer.Add(bottomup,flag=wx.ALIGN_CENTER)
		self.testsizer.Add(self.resulttext,flag=wx.ALIGN_CENTER)
		self.testsizer.Add(self.applybutton,flag=wx.ALIGN_CENTER)
		self.testsizer.Layout()
		self.test_ybutton.Hide()
		self.test_nbutton.Hide()
		self.applybutton.Hide()
		panel.SetSizer(self.testsizer)
		panel.SetAutoLayout(True)
	
	def onTestReset(self,event=False):
		self.test_ybutton.Hide()
		self.test_nbutton.Hide()
		self.applybutton.Hide()
		self.test_wordbutton.SetLabel("NEW TEST?")
		self.testingtext.SetLabel(self.testingstring % (str(self.cardvocab.user.testval),str(len(self.cardvocab.allwords)),str(self.cardvocab.language)))
	
	def onTestClick(self,event):
		button = event.GetEventObject()
		response=button.GetName()[:1]
		if response in ["y","n"]:
			self.testing.result(bool(response=="y"))
			next=self.testing.next()
			if not next:
				self.onTestEnd()
			else:
				self.test_wordbutton.SetLabel(self.testing.now_testing.mainform.encode("utf-8","ignore"))
				self.testing.card_direction=1
		elif response == "w": # wordbutton
			if self.test_wordbutton.GetLabel() == "NEW TEST?":
				self.testing = LevelTest(self.cardvocab,frame=self,thesebands=self.bandbox.GetChecked())
				self.testingtext.SetLabel("Test underway....")
				self.test_wordbutton.SetLabel(self.testing.now_testing.mainform.encode("utf-8","ignore"))
				self.test_ybutton.Show()
				self.test_nbutton.Show()
				self.testsizer.Layout()
			else: # standard click-to-flip behavior
				self.testing.card_direction = 0-self.testing.card_direction
				self.test_wordbutton.SetLabel({1:self.testing.now_testing.mainform.encode("utf-8","ignore"),-1:self.testing.now_testing.gloss.encode("utf-8","ignore")}[self.testing.card_direction])
	
	def onTestEnd(self,event=False):
		self.cardvocab.user.testval = 100*int(sum(self.testing.outcome.values())/100.0)
		self.testingtext.SetLabel(self.testingstring % (str(self.cardvocab.user.testval),str(len(self.cardvocab.allwords)),str(self.cardvocab.language)))
		resultstring = "You scored "
		for b in self.testing.bands:
			index = self.testing.bands.index(b)
			thisresult = "%s on band %s" % (int(self.testing.outcome[index]),index)
			if len(self.testing.bands) > 1:
				if b == self.testing.bands[-1]:
					thisresult = "and "+thisresult
				else:	
					thisresult += ", "
			resultstring+=thisresult
		resultstring+="."
		self.resulttext.SetLabel(resultstring)
		self.applybutton.Show()
		self.checkboxen={}
		boxoboxen=wx.StaticBox(self.testpanel)
		for r in self.testing.outcome:
			if float(self.testing.outcome[r])/len(self.testing.bands[r]) > 0.5:
				self.checkboxen[r] = wx.CheckBox(self.testpanel,label="Band %s (%s/%s)" % (r+1,self.testing.outcome[r],len(self.testing.bands[r])))
		checksizer=wx.StaticBoxSizer(boxoboxen,wx.HORIZONTAL)
		for c in self.checkboxen.values():
			checksizer.Add(c)
		self.testsizer.Add(checksizer,flag=wx.ALIGN_CENTER)
		self.testsizer.Remove(2)
		self.testsizer.Insert(2,(30,30))

		self.test_wordbutton.SetLabel("NEW TEST?")
		self.test_ybutton.Hide()
		self.test_nbutton.Hide()
		self.testsizer.Layout()
		
	def onTestApply(self,event):
		applybands = [self.testing.bands[x] for x in self.checkboxen.keys() if self.checkboxen[x].GetValue()]
		for a in applybands:
			print len(a),applybands.index(a)
			for word in a:
				try:
					self.solidify(word,update=False) # Avoid burden of processing 500 GUI updates.
					self.direction = self.sessiondirection
				except (IndexError,ValueError):
					print "IndexError on "+str(word)
		self.update()

# need to reset vocab, cardform, testform

	def onButton(self,event=False,response=False): # buttons in manager window main panel
		if event is not False:
			button = event.GetEventObject()
			response = button.GetName()[:1]
		print response
		if response =="1": #start test
			if not self.cardvocab.session.todo[1]:
				print "Nothing to do!"
			else:
				self.sessiondirection = 1
				self.resetCardForm(dothese=self.cardvocab.session.todo[1])
		elif response == "2": # test reverse
			if not self.cardvocab.session.todo[-1]:
				print "Nothing to do."
			else:
				self.sessiondirection = -1
				self.resetCardForm(dothese=self.cardvocab.session.todo[-1])
		elif response == "3" or response == "N": # practice slice
			self.sessiondirection = 1
			self.setupPractice()
		elif response == "R": # reset practice counter
			self.cardvocab.session.practiced=set()
			print "reset..."
			self.update()
		elif response=="f": # load new vocab file
			dialog = wx.FileDialog (self.cardpanel, message = 'Open vocabulary file', wildcard = "Text files (*.txt)|*.txt", style = wx.OPEN )
			if dialog.ShowModal() == wx.ID_OK:
				selected = dialog.GetPath()
				self.loadFile(selected)
			dialog.Destroy()
		elif response == "n": # "New day"
			daysworth = self.newdayinput.GetValue() # currently entered #words to get for new day
			try: 
				daysworth = int(daysworth)
				print "Daysworth: "+str(daysworth)
			except: 
				print "Error on daysworth "+str(daysworth)
			self.cardvocab.newsession(daysworth=daysworth)
			self.setupPractice()
			self.onSave() # threaded save.
		elif response == "o": # review old
			chunksize = int(self.oldinput.GetValue())
			available = self.cardvocab.review_old()
			if not available: 
				self.oldbutton.Disable()
			else:
				chunk = available[:chunksize]
				oldsession = pie.Session(self.cardvocab)
				oldsession.is_oldcheck = True
				self.cardvocab.current_word = chunk[0]
				self.resetCardForm(session=oldsession,is_oldcheck=True,dothese=chunk)
				if chunksize >= len(available):
					self.oldbutton.Disable()
					self.oldbutton.SetToolTip(wx.ToolTip("Oops -- none available at this time."))

	def drawPie(self):
		self.piesizer=wx.BoxSizer(wx.VERTICAL)
		togo=self.cardvocab.goal-self.cardvocab.donecount-self.cardvocab.activecount
		self.piepart1="Words to learn: %s" % str(togo)
		self.piepart2="Words learned: %s" % str(self.cardvocab.donecount)
		self.piepart3 = "Words in progress: %s" % self.cardvocab.activecount
		self.explode=(0.1,0.05,0.05)
		self.fracs=[togo,self.cardvocab.donecount,self.cardvocab.activecount]		
		self.pielabels=None
		self.pie=PiePanel(self.panel2,explode=self.explode,fracs=self.fracs,labels=self.pielabels,size=wx.Size(300,200),style=wx.EXPAND,figsize=(6,5),dpi=50)
		self.pie.SetBackgroundColour(self.color)

		therange=range(0,self.cardvocab.user.cycle)
		self.fracs2=[len([x for x in self.cardvocab.words if len(x.successes)==y]) for y in therange]
		self.explode2=tuple([0.1 for x in therange])
		self.pielabels2=[str(x)+" wins\n(%s cards)" % str(len([y for y in self.cardvocab.words if len(y.successes)==x])) for x in therange]
		self.pie2=PiePanel(self.panel2,explode=self.explode2,fracs=self.fracs2,labels=self.pielabels2,size=wx.Size(300,200),style=wx.EXPAND,figsize=(6,5),dpi=50)
		self.pie2.SetBackgroundColour(self.color)

		self.piesizer.Add(self.pie,flag=wx.EXPAND)
		self.piesizer.Add(self.pie2,flag=wx.EXPAND)
		self.piesizer.Layout()
		self.panel2.SetSizer(self.piesizer)
		self.panel2.SetAutoLayout(True)
		self.piesizer.Fit(self.panel2)

	def updatePie(self):
		self.fracs=[self.cardvocab.goal-self.cardvocab.donecount-self.cardvocab.activecount,self.cardvocab.donecount,self.cardvocab.activecount]
		self.pie.redraw(self.explode,self.fracs,self.pielabels)

	def applyChanges(self,event): # editor button bindings
		button = event.GetEventObject()
		response=button.GetName()[:1]
		print response
		if response == "a" or response == "s":
			for word in [x for x in self.cardvocab.words if self.wordboxes[x]]:
				if self.wordboxes[word].checkbox.GetValue():
					self.cardvocab.delete(word)
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
					self.cardvocab.save()
				except:
					print "Unable to save."
		self.panel3.Refresh()
#		self.buildSettings()
		return response
	
	def loadFile(self,selected):
		if hasattr(self,"filer"):
			self.filer.SetLabel(selected)
		try:
			newwords=pie.Vocabulary(restorefrom=selected)
			if newwords:
				del self.cardvocab
				self.cardvocab=newwords
				self.cardvocab.path=selected
				self.session=self.cardvocab.session
				self.do_these=list(self.cardvocab.words)
				if not self.do_these:
					self.cardvocab.newsession()
					self.dothese()
				self.cardvocab.current_word = self.do_these[0]
				self.cardvocab=self.cardvocab
				self.exemplify()
				self.update()
			elif hasattr(self,"filer"):
				self.update()
		except KeyboardInterrupt:
			print "Exception when loading file! "+selected, e
			if hasattr(self,"filer"):
				self.filelabel="Invalid file."
				self.filebefore.SetLabel(self.filelabel)
				self.update()
	
	def saveFile(self):
		directory=os.getcwd()
		dialog = wx.FileDialog (self.cardpanel, message = 'Save vocabulary file', wildcard = "Text files (*.txt)|*.txt", style = wx.SAVE | wx.FD_OVERWRITE_PROMPT | wx.FD_CHANGE_DIR )
		outcome=dialog.ShowModal()
		if outcome == wx.ID_OK:
				selected = dialog.GetPath()
				print selected
				self.cardvocab.path=selected
				output=self.cardvocab.dump()
				outfile=open(selected,"w")
				with outfile:
					outfile.write(output)
		dialog.Destroy()			

class HtmlWin(HtmlWindow):
	def __init__(self, parent):
		wx.html.HtmlWindow.__init__(self,parent, wx.ID_ANY)
		if "gtk2" in wx.PlatformInfo:
			self.SetStandardFonts()

	def OnLinkClicked(self, link):
		wx.LaunchDefaultBrowser(link.GetHref())

class PiePanel (wx.Panel):
	def __init__( self, parent, color=None, colors=None, figsize= (4,4), dpi=None, explode=(0.1, 0.1, 0.1, 0.1), fracs=[15,30,45, 10], labels=('Frogs', 'Hogs', 'Dogs', 'Logs'),**kwargs ):
		from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
		from matplotlib.figure import Figure
		if 'id' not in kwargs.keys():
			kwargs['id'] = wx.ID_ANY
		wx.Panel.__init__( self, parent, **kwargs )
		self.parent=parent
		self.figure = Figure( figsize, dpi )
		self.canvas = FigureCanvasWxAgg( self, -1, self.figure )
		self.SetColor( color )
		self.colors=colors
		self.ax = self.figure.add_axes([0.1, 0.1, 0.8, 0.8])
		self.pielets=self.ax.pie(fracs, explode=explode, labels=labels, colors=colors, shadow=True)
		self.draw()

	def SetColor( self, rgbtuple=None ):
		if rgbtuple is None:
			rgbtuple = wx.SystemSettings.GetColour( wx.SYS_COLOUR_BTNFACE ).Get()
		clr = [c/255.0 for c in rgbtuple]
		self.figure.set_facecolor( clr )
		self.figure.set_edgecolor( clr )
		self.canvas.SetBackgroundColour( wx.Colour( *rgbtuple ) )
	
	def redraw(self,explode=False,fracs=False,labels=False):
		if explode:
			self.explode=explode
		if fracs:
			self.fracs=fracs
		if labels:
			self.labels=labels
		self.pielets=self.ax.pie(fracs, explode=explode, labels=labels, shadow=True)
		self.draw()

	def draw( self ):
		print "Drawing", str(self.GetSize())
		self.canvas.draw()

# -- Testing object(s) -- #

class LevelTest:
	def __init__(self,vocab,frame=False,bandwidth=500,thesebands=[]):
		self.done=set()
		self.wordlist=[]
		self.bandwidth=bandwidth
		self.cardvocab=vocab
		self.bands=vocab.bands(self.bandwidth)
		if len(thesebands) > 0: # manual override
			print "Thesebands: "+str(thesebands)
			self.bands=[x for x in self.bands if self.bands.index(x) in thesebands]
			print len(self.bands)
		self.card_direction=1
		self.frame=frame
		self.current_band=0 # index of current band
		self.current_batch=self.buildlist()
		self.outcome=dict([(self.bands.index(x),0) for x in self.bands])
		self.now_testing=self.current_batch[0]
		self.yes=0
		self.loopcheck=0

	def buildlist(self):
		words=list(self.bands[self.current_band])
		random.shuffle(words)
		return words[:10]
	
	def result(self,result): # report back result
		if result:
			self.yes+=1
	
	def next(self): # advance current word by one
		if self.now_testing != self.current_batch[-1]:
			self.now_testing = self.current_batch[self.current_batch.index(self.now_testing)+1]
		else: # end of band
			if self.yes < 3: 
				return False
			self.outcome[self.current_band]=self.yes*(len(self.bands[self.current_band])/10.0) # total estimated number of known words in the band
			print self.current_band, self.outcome[self.current_band], self.yes
			new=self.newband()
			if not new: return False
		self.card_direction=1
		return True
		
	def newband(self):
		self.yes=0
		direction=1
		if self.current_band > 0 and self.outcome[self.current_band]-self.outcome[self.current_band-1] > 10: # going backwards
			self.loopcheck+=1
			if self.loopcheck > 3:
				direction=-1
		self.current_band+=direction # (+1 or -1)
		if self.current_band < 0 or self.current_band > len(self.bands)-1: 
			return False # no more to do
		self.current_batch=self.buildlist()
		self.now_testing=self.current_batch[0]
		return True


class CardEditForm(wx.Frame):  
	def __init__(self,parent,vocab,word,thelist): # "word" must be a member of "thelist"
		print "Creating cardform"
		self.parent = parent
		self.vocab = vocab
		self.word = word
		if self.word not in thelist:
			print "Unable to instantiate edit form, word not in list."
			self=False
			return False
		self.thelist = thelist
#foundations for display		
		titlestring = "Editing flashcard for %s" % word.mainform.encode("utf-8","ignore")		
		wx.Frame.__init__(self, parent, wx.ID_ANY, titlestring,size=wx.Size(400,700))
		self.SetIcon(self.parent.icon)
		self.panel = wx.Panel(self, wx.ID_ANY) # need a panel to enable tab traversla
		self.mainformtext = wx.StaticText(self.panel,label="Main form: ")
		self.exampletext = wx.StaticText(self.panel,label="Selected examples: ")
		self.phontext = wx.StaticText(self.panel,label="Phonetic form: ")
		self.romtext = wx.StaticText(self.panel,label="Romanization: ")
		self.glosstext = wx.StaticText(self.panel,label="Main gloss: ")
		self.glossestext = wx.StaticText(self.panel,label="List of meanings: ")
		
		self.savebutton = wx.Button(self.panel,id=wx.ID_SAVE, label="Apply")
		self.cancelbutton = wx.Button(self.panel,id=wx.ID_CANCEL)
		self.nextbutton = wx.Button(self.panel,label="Next card")
		self.backbutton = wx.Button(self.panel,label="Previous card")
		self.savebutton.Bind(wx.EVT_BUTTON,self.onEditSave)
		self.cancelbutton.Bind(wx.EVT_BUTTON,self.onEditCancel)
		self.nextbutton.Bind(wx.EVT_BUTTON,self.onEditNext)
		self.backbutton.Bind(wx.EVT_BUTTON,self.onEditBack)
		self.is_active = wx.CheckBox(self.panel,label="In active review.")
		self.is_active.SetValue(bool(word.status==1))
		
		if self.word == self.thelist[0]:
			self.backbutton.Disable()
		if self.word == self.thelist[-1]:
			self.nextbutton.Disable()
		
		self.mainforminput = wx.TextCtrl(self.panel,value=word.mainform.encode("utf-8","ignore"),size=wx.Size(200,20))
		self.phoninput = wx.TextCtrl(self.panel,value=word.phonetic.encode("utf-8","ignore"),size=wx.Size(200,20))
		self.rominput = wx.TextCtrl(self.panel,value=word.rom.encode("utf-8","ignore"),size=wx.Size(200,20))
		self.glossinput = wx.TextCtrl(self.panel,value=word.gloss.encode("utf-8","ignore"),size=wx.Size(200,20))
		self.glossesinput = wx.TextCtrl(self.panel,value=word.glossed.encode("utf-8","ignore"),size=wx.Size(200,60),style=wx.TE_MULTILINE)
		
		self.examplesbox = wx.StaticBox(self.panel)
		self.examples = []
		word_examples = word.examples
		word_examples.extend([pie.Example("")])
		for e in word_examples:
			example_box = wx.TextCtrl(self.panel,value=e.text.encode("utf-8","ignore"))
			href_box = wx.TextCtrl(self.panel,value=e.href)
			priority_box = wx.Choice(self.panel,choices=[str(x) for x in range(1,11)])
			priority_box.SetSelection(e.priority)
			delete_check = wx.CheckBox(self.panel,label="Delete")
			if not e.text: delete_check.Disable()
			self.examples.append((delete_check,example_box,href_box,priority_box))
			
		self.notesbox = wx.StaticBox(self.panel)
		self.notes = list(word.notes)
		self.notestext = wx.StaticText(self.panel, label="Notes for this card.")
		self.notes.append(pie.Note("", 0, self.parent.cardsession.id)) # one for adding
		self.noteboxen = {}
		for n in self.notes:
			show1_check = wx.CheckBox(self.panel,label="Show on forward")
			show2_check = wx.CheckBox(self.panel,label="Show on reverse")
			showprac_check = wx.CheckBox(self.panel,label="Show on practice only")
			delete_check = wx.CheckBox(self.panel,label="Delete")
			if not n.text: delete_check.Disable()
			notetext = wx.TextCtrl(self.panel,value=n.text)
			self.noteboxen[n] = (show1_check, show2_check, showprac_check, delete_check, notetext)
		
		mainsizer = wx.BoxSizer(wx.VERTICAL)
		buttonsizer1 = wx.BoxSizer(wx.HORIZONTAL)
		buttonsizer1.Add(self.backbutton)
		buttonsizer1.Add(self.nextbutton)
		buttonsizer1.Add(self.savebutton)
		buttonsizer1.Add(self.cancelbutton)
		detailsizer = wx.BoxSizer(wx.HORIZONTAL)
		
		mainsizer.Add(buttonsizer1)
		mainsizer.Add(self.mainformtext)
		mainsizer.Add(self.mainforminput)
		mainsizer.Add(self.phontext)
		mainsizer.Add(self.phoninput)
		mainsizer.Add(self.romtext)
		mainsizer.Add(self.rominput)
		mainsizer.Add(self.glosstext)
		mainsizer.Add(self.glossinput)
		mainsizer.Add(self.glossestext)
		mainsizer.Add(self.glossesinput)
		mainsizer.Add(self.is_active)
		
		examplesizer = wx.StaticBoxSizer(self.examplesbox,wx.VERTICAL)
		examplesizer.Add(self.exampletext)
		for e in self.examples:
			thesizer = wx.BoxSizer(wx.HORIZONTAL)
			thesizer.AddMany([(x,) for x in e])
			examplesizer.Add(thesizer)
		detailsizer.Add(examplesizer)
		mainsizer.Add(detailsizer)
		
		notesizer = wx.StaticBoxSizer(self.notesbox, wx.VERTICAL)
		notesizer.Add(self.notestext)
		for n in self.noteboxen.keys():
			thesizer = wx.BoxSizer(wx.HORIZONTAL)
			thelittlesizer = wx.BoxSizer(wx.VERTICAL)
			thesizer.AddMany([(x,) for x in self.noteboxen[n][:-1]])
			thelittlesizer.Add(thesizer)
			thelittlesizer.Add(self.noteboxen[n][-1],1,flag=wx.EXPAND)
			notesizer.Add(thelittlesizer)
		mainsizer.Add(notesizer)
		
		mainsizer.Layout()
		self.panel.SetSizer(mainsizer)
		self.Bind(wx.EVT_MENU, self.onEditCancel, id=99)
		self.Bind(wx.EVT_MENU, self.onEditSave, id=101)
		accel_tbl = wx.AcceleratorTable([
									(wx.ACCEL_CTRL, ord('X'), 99),
									(wx.ACCEL_CTRL, ord('S'), 101),
								])
		self.SetAcceleratorTable(accel_tbl)
		
	def reset(self,word):
		self.word=word
		if self.word == self.thelist[0]:
			self.backbutton.Disable()
		if self.word == self.thelist[-1]:
			self.nextbutton.Disable()
		self.mainforminput.SetValue(word.mainform.encode("utf-8","ignore"))
		self.phoninput.SetValue(word.phonetic.encode("utf-8","ignore"))
		self.rominput.SetValue(word.rom.encode("utf-8","ignore"))
		self.glossinput.SetValue(word.gloss.encode("utf-8","ignore"))
		self.glossesinput.SetValue(word.glossed.encode("utf-8","ignore"))
		word_examples = word.examples
		word_examples.extend((10-len(word.examples))*[pie.Example("")])
		for e in word_examples:
			index = word_examples.index(e)
			self.examples[index][0].SetValue(False)
			self.examples[index][1].SetValue(e.text.encode("utf-8","ignore"))
			self.examples[index][2].SetValue(e.href)
			self.examples[index][3].SetSelection(e.priority)
		self.savebutton.Enable()
		self.cancelbutton.Enable()

	def onEditSave(self,event):
		self.word.mainform = self.mainforminput.GetValue()
		self.word.phonetic = self.phoninput.GetValue()
		self.word.rom = self.rominput.GetValue()
		self.word.gloss = self.glossinput.GetValue()
		self.word.glossed = self.glossesinput.GetValue()
		examples_temp = []
		for e in self.examples:
			if e[0].GetValue(): 
				continue # has been marked for deletion
			elif not e[1].GetValue(): 
				continue # is blank
			newex = pie.Example("")
			newex.text = e[1].GetValue().strip()
			newex.href = e[2].GetValue().strip()
			newex.priority=int(e[3].GetSelection()) # note this is the index (0-9) rather than the shown value (1-10) 
			examples_temp.append(newex)
		self.word.examples = examples_temp
			
		for n in self.noteboxen.keys():
			notebox = self.noteboxen[n]
			delete = notebox[3].GetValue()
			if delete:
				print "Deleting note..."
				if n in self.word.notes:
					self.word.notes.remove(n)
				continue
			text = notebox[4].GetValue()
			if text and n not in self.word.notes:
				print "Adding note..."
				self.word.notes.append(n)
			n.text = text
			n.showforward = notebox[0].GetValue()
			n.showbackward = notebox[1].GetValue()
			n.practiceonly = notebox[2].GetValue()
			n.props2type()
		self.parent.update()
		self.savebutton.Disable()
		self.cancelbutton.Disable()
		self.parent.editform = False
		self.Destroy()
	
	def onEditCancel(self,event):
		self.parent.editform = False # reset so that edit form can be opened afresh
		self.Destroy()

	def onEditNext(self,event):
		try:
			self.word = self.thelist[self.thelist.index(self.word)+1]
		except IndexError:
			print "Unable to advance!"
			self.nextbutton.Disable()
		else:
			self.reset(self.word)
		
	def onEditBack(self,event):
		try:
			self.word = self.thelist[self.thelist.index(self.word)-1]
		except IndexError:
			print "Unable to reverse!"
			self.backbutton.Disable()
		else:
			self.reset(self.word)

	def onKeyPress(self,event):
		self.savebutton.Enable()
		self.cancelbutton.Enable()

class SettingsForm(wx.Frame):  
	def __init__(self,parent,vocab): # "word" must be a member of "thelist"
		print "Creating settingsform"
		self.parent = parent
		self.vocab = vocab
#foundations for display		
		titlestring = "Editing settings for %s, learning %s" % (str(self.vocab.user), str(self.vocab.language))
		wx.Frame.__init__(self, parent, wx.ID_ANY, titlestring,size=wx.Size(500,500))
		self.SetIcon(self.parent.icon)
		
		self.savebutton = wx.Button(self,id=wx.ID_SAVE, label="Apply")
		self.cancelbutton = wx.Button(self,id=wx.ID_CANCEL)
		self.savebutton.Bind(wx.EVT_BUTTON, self.applySettings)
		self.cancelbutton.Bind(wx.EVT_BUTTON, self.onCancel)

		mainsizer=wx.BoxSizer(wx.VERTICAL)

		buttonsizer=wx.BoxSizer(wx.HORIZONTAL)
		buttonsizer.Add(self.savebutton)
		buttonsizer.Add((5,5)) 		
		buttonsizer.Add(self.cancelbutton)
		mainsizer.Add(buttonsizer)
		mainsizer.Add((5,5))

# setting up the settings
		cyclestring="Number of consecutive days of accurate recall required before a word is considered known: "
		cycletext=wx.StaticText(self, label=cyclestring)
		self.cyclefield=wx.TextCtrl(self, value=str(self.vocab.user.cycle),size=wx.Size(150,20))
		perdiemstring="Number of new words to be added per day: "
		perdiemtext=wx.StaticText(self, label=perdiemstring)
		self.perdiemfield=wx.TextCtrl(self,value=str(self.vocab.user.perdiem),size=wx.Size(150,20))
		goalstring="Number of words to be learned: "
		goaltext=wx.StaticText(self, label=goalstring)
		self.goalfield=wx.TextCtrl(self, value=str(self.vocab.goal),size=wx.Size(150,20))
		targetstring="Target level of reading ability: "
		targettext=wx.StaticText(self, label=targetstring)
		self.targetfield=wx.TextCtrl(self, value="", size=wx.Size(150,20))

		mainsizer.Add(cycletext)
		mainsizer.Add(self.cyclefield)
		mainsizer.Add((5,5))
		mainsizer.Add(perdiemtext)
		mainsizer.Add(self.perdiemfield)
		mainsizer.Add((5,5))
		mainsizer.Add(goaltext)
		mainsizer.Add(self.goalfield)
		mainsizer.Add((5,5))
		mainsizer.Add(targettext)
		mainsizer.Add(self.targetfield)
		mainsizer.Layout()

		self.Bind(wx.EVT_MENU, self.onCancel, id=99)
		self.Bind(wx.EVT_MENU, self.applySettings, id=101)
		accel_tbl = wx.AcceleratorTable([
									(wx.ACCEL_CTRL, ord('X'), 99),
									(wx.ACCEL_CTRL, ord('S'), 101),
								])
		self.SetAcceleratorTable(accel_tbl)

		self.SetSizer(mainsizer)
		self.SetAutoLayout(True)
		self.SetBackgroundColour(self.parent.color)

	def applySettings(self,event=False):
		self.parent.cardvocab.user.perdiem = int(self.perdiemfield.GetValue())
		self.parent.cardvocab.user.cycle = int(self.cyclefield.GetValue())
		self.Destroy()
		
	def onCancel(self,event=False):
		self.Destroy()
		
# -- End of class definitions -- #

# miscellaneous utility functions

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
		foo=pie.Vocabulary(restorefrom=file)
	except:
		foo=pie.Vocabulary()
	foo.run()
	
if __name__ == "__main__" :
	import sys
	outfile=open("latest_log.txt","a")
	sys.stdout=outfile
	sys.stderr=outfile
	print datetime.datetime.today().isoformat()
	run3()
