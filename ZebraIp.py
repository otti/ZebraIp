import socket

class Zebra:

    _default_port = 9100
    _host = ""
    _port = _default_port


    _dots_per_inch = 203
    _dots_per_mm   =  _dots_per_inch/25.4

    _print_head_width = 447 # 2.2" * 203 dpi

    _label_width  = 0 # dots
    _label_height = 0 # dots

    _buffer = b''
    _debug_en = False
    _unit = 'imperial'

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def __init__(self, host, port=_default_port, unit="imperial", debug=True):
        self._host     = host
        self._port     = port
        self._debug_en = debug
        self._unit     = unit
        try:
            self.s.connect((self._host, self._port))
        except:
            print("Not connected")

    def __del__(self):
        self.s.close()
    
    def pos_to_dots(self, pos):
        if self._unit == "imperial":
            return int(pos)
        else:
            return int(float(pos) * (float(self._dots_per_mm)))

    def dbg_print(self, text):
        if self._debug_en:
            print(text)
    
    def SendToPrinter(self, cmd):
        if isinstance(cmd, str) :
            self.s.sendall(cmd.encode("latin_1"))
        elif isinstance(cmd, bytes):
            self.s.sendall(cmd)


    def LabelInit(self, width, height, gap, x_offset=None, y_offset=None):

        if self._unit != "imperial": # --> is metric
            height = self.pos_to_dots(height)
            width  = self.pos_to_dots(width)
            gap    = self.pos_to_dots(gap)

            if x_offset != None:
                x_offset = self.pos_to_dots(x_offset)
            if y_offset != None:
                y_offset = self.pos_to_dots(y_offset)

        self._label_width  = width
        self._label_height = height
        cmd = '\nOD\n'                              # Enable Direct Thermal Mode
        cmd += 'Q%s,%s\n'%(int(height), int(gap))   # Set label height and gap width

        # Use "q" command and expect the label to be in the center of the print head
        if x_offset == None and y_offset == None:
            cmd += 'q%s\n'%int(width)               # Set laben width
            self.dbg_print('Width:%d Height: %d, Gap: %d\n'%(width, height, gap))
        else:
        # Use "R" commmand and adjust teh left and top offset
            if x_offset == None:
                print("At least x_offset has to be set")
                exit(1)
            if y_offset == None:
                y_offset = 0

            x_offset = int(((self._print_head_width - self._label_width)/2) + x_offset)

            if x_offset < 0:
                print("x_offset is outside of printable area")
                exit(1)                

            cmd += 'R%s,%s\n'%(int(x_offset), int(y_offset)) # Set offset from referenceposition
            self.dbg_print('Width:%d Height: %d, Gap: %d, X Offset: %d, Y Offset: %d\n'%(width, height, gap, x_offset, y_offset))

        self.dbg_print(cmd)
        self.SendToPrinter(cmd) 

    # Autodetect label and gap length
    def Autosense(self):
         self.SendToPrinter('\nxa\n')

    # send 1 bit PCX to the printer. Can be generated with Gimp
    # Deleting and Writing files will reduce the flash lifetime!
    def StoreGraphics(self, name, filename):
        assert filename.lower().endswith('.pcx')
        cmd = '\nGK"%s"\n'%name                # Delete file
        cmd += 'GK"%s"\n'%name                 # delete mus be called twice
        size = os.path.getsize(filename)
        cmd += 'GM"%s"%s\n'%(name,size)        # Store graphics
        cmd += open(filename,'rb').read()
        self.SendToPrinter(cmd)

    # Print graphic direct without storing a file in Flash
    # x, y:   Top left corner
    # width:  Width in dots. Must be a multiple of 8
    # length: Length in dots 
    # data:   raw data
    def AddGraphic(self, x, y, width, height, data):
        assert type(data) == bytes
        assert width % 8 == 0  # make sure width is a multiple of 8
        assert (width//8) * height == len(data)
        x      = self.pos_to_dots(x)
        y      = self.pos_to_dots(y)
        width  = self.pos_to_dots(width)
        height = self.pos_to_dots(height)

        cmd = b"GW%d,%d,%d,%d,%s\n"%(x, y, width//8, height, data)
        self.AddToBuffer(cmd)
    
    # Print the Bitmap as ASCII Art
    def DbgPrintAsciiArt(self, data, width, out_filename):
        if self._debug_en:
            bmp = ''
            for i in range(0, len(data)):
                raw = int.from_bytes(data[i:i+1], byteorder='little', signed=False)
                for x in range(0, 8):
                    if raw & (0x80>>x):
                        bmp = bmp + ' '
                    else:
                        bmp = bmp + 'x'
                if ((i+1) % (width/8) == 0) and (i != 0):
                    bmp = bmp + '\n'
            
            with open(out_filename, 'w') as f:
                f.write(bmp)

    # Add bitmap to buffer
    # The width must be a multiple of 8
    # only balck and white image wit windows header are supported yet!
    # Gimp: Image -> Mode -> Indexed; File -> Export as -> MyFilename.bmp
    def AddBitmap(self, x, y, filename):
        x = self.pos_to_dots(x)
        y = self.pos_to_dots(y)
        self.dbg_print("PrintBitmap:")
        assert filename.lower().endswith('.bmp')
        data = open(filename,'rb').read()

        header = int.from_bytes(data[0x00:0x02], byteorder='little', signed=False)
        self.dbg_print("   BMP Header: " + str(hex(header)))
        if header != 0x4d42:
            print("Only windows BMPs are supported yet!")
            return

        file_size = int.from_bytes(data[0x02:0x06], byteorder='little', signed=False)
        self.dbg_print('   Filesize: %s (%s)'%(str(file_size), str(hex(file_size)) ))

        data_offset = int.from_bytes(data[0x0A:0x0E], byteorder='little', signed=False)
        self.dbg_print("   Raw Data offset: " + str(hex(data_offset)))
        
        data_len = file_size - data_offset
        self.dbg_print("   Raw Data Len: " + str(data_len) + " Byte --> " + str(data_len*8) + " Pixels")

        width = int.from_bytes(data[0x12:0x16], byteorder='little', signed=False)
        height = int.from_bytes(data[0x16:0x1A], byteorder='little', signed=False)
        self.dbg_print("   HeightxWidth: %dx%d"%(height, width))

        if width % 8 != 0 :
            print("Image width must be a multiple of 8")
            return

        bit_per_pixel = int.from_bytes(data[0x1C:0x1E], byteorder='little', signed=False)
        self.dbg_print("   BitsPerPixel: " + str(bit_per_pixel))

        if bit_per_pixel != 1:
            print("Image must be black and white (1 bit per pixel)")
            return
        
        RowSize = int(((bit_per_pixel * width + 31) / 32)) * 4
        self.dbg_print("   RowSize: " + str(RowSize))
        
        # each row in the bmp is alway a multiple of 4 bytes
        # if this is not completely used, padding bytes will be added
        # --> remove padding bytes
        data_raw = b''
        for row in range(0, height):
            start_idx = int(data_offset + row*RowSize)
            end_idx = int(start_idx + (width/8)) 
            data_raw = data_raw +  data[start_idx:end_idx]
        
        self.DbgPrintAsciiArt(data_raw, width, filename + "_asciiart_reverse.txt")

        #BMP is stored "bottom-up" --> Reverse
        rev_data = b''
        for row in range(0, height):
            start_idx = int((((height-1)-row)*(width/8)))
            end_idx = int(start_idx + (width/8))
            rev_data = rev_data + data_raw[start_idx:end_idx]

        self.DbgPrintAsciiArt(rev_data, width, filename + "_asciiart.txt")
        self.AddGraphic(x, y, width, height, rev_data)
        
    def ClearBuffer(self):
        self.AddToBuffer('\nN\n')
    
    def Print(self, NoOfLabels=1):
        self.AddToBuffer("P%d\n"%(NoOfLabels))
        self.dbg_print(self._buffer)
        self.SendToPrinter(self._buffer)
    
    def AddToBuffer(self, cmd):
        if isinstance(cmd, str) :
            cmd = cmd.encode("latin_1")
        self._buffer = self._buffer + cmd
    
    def AddText(self, x, y, text, font=4, rot=0, reverse=False):

        if not isinstance(text, str):
            print("Parameter \"text\" must be of type str")

        y = self.pos_to_dots(y)

        if isinstance(x, str):
            if x.lower() == "center":
                font_width = [0, 8, 10, 12, 14, 32] # in px
                if font>=1 and font<=5:
                    text_width = len(text) * font_width[font]
                    x = int((self._label_width/2) - (text_width/2))
                    if x < 0:
                        x = 0
            else:
                print("Invalid value or type for parameter x. Must be int or \"center\"")
                exit(1)
        else:
            x = self.pos_to_dots(x)

        if reverse:
            reverse = "R"
        else:
            reverse = "N"

        self.AddToBuffer("A%d,%d,%d,%d,%d,%d,%s,\"%s\"\n"%(x, y, rot, font, 1, 1, reverse, text))

    def AddQrCode(self, x, y, data, Scale=3, ErrCorLev="M"):
        x = self.pos_to_dots(x)
        y = self.pos_to_dots(y)
        self.AddToBuffer("b%d,%d,%s,%d,%d,%s,%s,%s,\"%s\"\n"%(x, y,"Q", 2, Scale, ErrCorLev, "A", "c", data))

    def AddHorLine(self, x, y, length, thickness):
        x      = self.pos_to_dots(x)
        y      = self.pos_to_dots(y)
        length = self.pos_to_dots(length)
        self.AddToBuffer("LO%d,%d,%d,%d\n"%(x, y, length, thickness))

    def AddVertLine(self, x, y, length, thickness):
        x      = self.pos_to_dots(x)
        y      = self.pos_to_dots(y)
        length = self.pos_to_dots(length)     
        self.AddToBuffer("LO%d,%d,%d,%d\n"%(x, y, thickness, length))

    def AddDiagLine(self, x, y, xLen, yLen, thickness): 
        x      = self.pos_to_dots(x)
        y      = self.pos_to_dots(y)
        xLen = self.pos_to_dots(xLen)
        yLen = self.pos_to_dots(yLen)
        self.AddToBuffer("LS%d,%d,%d,%d,%d\n"%(x, y, thickness, x+xLen, y+yLen))

    def AddBox(self, x, y, width, hight, thickness): 
        x     = self.pos_to_dots(x)
        y     = self.pos_to_dots(y)
        width = self.pos_to_dots(width)
        hight = self.pos_to_dots(hight)      
        self.AddToBuffer("X%d,%d,%d,%d,%d\n"%(x, y, thickness, x+width, y+hight))

    def EnableDhcp(self, DevName):
        #untested!
        #Command extracted from Zebra Setup utilities
        cmd = "\rN\n^XA\n^ND2,A\n^NBC\n^NC1\n^NPP\n^NN%s\n^XZ\n^XA\n^JUS\n^XZ\n"%(DevName)
        self.SendToPrinter(cmd)
    
    def AddCode128(self, x, y, height, data, rot=0, BarWidth=2, PrintText=False):
        x     = self.pos_to_dots(x)
        y     = self.pos_to_dots(y)
        hight = self.pos_to_dots(hight)  
        if PrintText:
            PrintText = "B"
        else:
            PrintText = "N"
        self.AddToBuffer("B%d,%d,%d,%s,%d,%s,%d,%s,\"%s\"\n"%(x, y, rot, "1", BarWidth,5, height, PrintText, data))

    def AddEan13(self, x, y, height, data, rot=0, BarWidth=2, PrintText=False):
        x     = self.pos_to_dots(x)
        y     = self.pos_to_dots(y)
        hight = self.pos_to_dots(hight) 
        if len(data)!=12 and len(data)!=13:
            print("EAN13 has to have exactly 12 or 13 digits")
            exit(1)
        
        if not data.isdigit():
            print("EAN13 only allows numbers")
            exit(1)

        if PrintText:
            PrintText = "B"
        else:
            PrintText = "N"
        self.AddToBuffer("B%d,%d,%d,%s,%d,%s,%d,%s,\"%s\"\n"%(x, y, rot, "E30", BarWidth,5, height, PrintText, data))
# Main
# ------------------------------------------------------------------


if __name__ == '__main__':
    HOST = "zebra.lan"
    PORT = 9100

    p = Zebra(HOST, PORT) # use parameter "unit" to switch to metric
    p.LabelInit(319, 200, 16) # 25x40 mm wih 2 mm gap

    # use these handy functions ....
    # ------------------------------
    p.ClearBuffer()
    p.AddBitmap   (0,   0,   "Tux.bmp")
    p.AddText     (0,   120, "FooBar")
    p.AddText     (0,   150, "FooBar", reverse=True)
    p.AddText     (230, 50,  "FooBar", rot=1)
    p.AddQrCode   (120, 10,  123456)
    p.AddBox      (120, 100,  50, 40, 2)
    p.AddDiagLine (120, 100,  50, 40, 2)
    p.AddDiagLine (170, 100, -50, 40, 2)
    p.AddHorLine  (120, 120,  50, 2)
    p.AddVertLine (145, 100,  40, 2)
    p.Print()

    # ... or do it like a pro :-)
    # ------------------------------
    label = """
N
A40,0,0,4,1,1,N, "123456789"
P1
"""
    p.SendToPrinter(label)
