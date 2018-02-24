import matplotlib
matplotlib.interactive( True )
matplotlib.use( 'WXAgg' )

import numpy as num
import wx
import matplotlib.pyplot

class PiePanel (wx.Panel):
    def __init__( self, parent, color=None, dpi=None, explode=(0, 0.05, 0, 0), fracs=[15,30,45, 10], **kwargs ):
        from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
        from matplotlib.figure import Figure
        if 'id' not in kwargs.keys():
            kwargs['id'] = wx.ID_ANY
        if 'style' not in kwargs.keys():
            kwargs['style'] = wx.NO_FULL_REPAINT_ON_RESIZE
        wx.Panel.__init__( self, parent, **kwargs )
        self.parent=parent
        self.figure = Figure( None, dpi )
        self.canvas = FigureCanvasWxAgg( self, -1, self.figure )
        labels = 'Frogs', 'Hogs', 'Dogs', 'Logs'
        self.SetColor( color )
        self._SetSize()
        ax = self.figure.add_axes([0.1, 0.1, 0.8, 0.8])
        pies=ax.pie(fracs, explode=explode, labels=labels, autopct='%1.1f%%', shadow=True)
        self.draw()
        self._resizeflag = False
        self.Bind(wx.EVT_IDLE, self._onIdle)
        self.Bind(wx.EVT_SIZE, self._onSize)

    def SetColor( self, rgbtuple=None ):
        """Set figure and canvas colours to be the same."""
        if rgbtuple is None:
            rgbtuple = wx.SystemSettings.GetColour( wx.SYS_COLOUR_BTNFACE ).Get()
        clr = [c/255. for c in rgbtuple]
        self.figure.set_facecolor( clr )
        self.figure.set_edgecolor( clr )
        self.canvas.SetBackgroundColour( wx.Colour( *rgbtuple ) )

    def _onSize( self, event ):
        self._resizeflag = True

    def _onIdle( self, evt ):
        if self._resizeflag:
            self._resizeflag = False
            self._SetSize()

    def _SetSize( self ):
        pixels = tuple( self.parent.GetClientSize() )
        self.SetSize( pixels )
        self.canvas.SetSize( pixels )
        self.figure.set_size_inches( float( pixels[0] )/self.figure.get_dpi(),
                                     float( pixels[1] )/self.figure.get_dpi() )
        def draw( self ):
            print "Drawing"
            self.canvas.draw()

def test():
    app = wx.PySimpleApp( 0 )
    frame = wx.Frame( None, wx.ID_ANY, 'WxPython and Matplotlib', size=(300,300) )
    panel = DemoPlotPanel( frame)
    frame.Show()
    app.MainLoop()

                
if __name__ == '__main__':

    theta = num.arange( 0, 45*2*num.pi, 0.02 )

    rad0 = (0.8*theta/(2*num.pi) + 1)
    r0 = rad0*(8 + num.sin( theta*7 + rad0/1.8 ))
    x0 = r0*num.cos( theta )
    y0 = r0*num.sin( theta )

    rad1 = (0.8*theta/(2*num.pi) + 1)
    r1 = rad1*(6 + num.sin( theta*7 + rad1/1.9 ))
    x1 = r1*num.cos( theta )
    y1 = r1*num.sin( theta )

    points = [[(xi,yi) for xi,yi in zip( x0, y0 )],
              [(xi,yi) for xi,yi in zip( x1, y1 )]]
    clrs = [[225,200,160], [219,112,147]]

    app = wx.PySimpleApp( 0 )
    frame = wx.Frame( None, wx.ID_ANY, 'WxPython and Matplotlib', size=(300,300) )
    panel = DemoPlotPanel( frame, points, clrs )
    frame.Show()
    app.MainLoop()

