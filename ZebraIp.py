import socket

class Zebra:

    DEFAULT_PORT = 9100
    HOST = ""
    PORT = DEFAULT_PORT

    DEFAULT_DOTS_PER_INCH = 203 # defaut for LP 2824
    DOTS_PER_INCH = 203

    DOTS_PER_MM = 0

    BUFFER = b''

    DEBUG_EN = False

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def __init__(self, host, port=DEFAULT_PORT, dpi=DEFAULT_DOTS_PER_INCH, debug=False):
        self.HOST = host
        self.PORT = port
        self.DOTS_PER_INCH = dpi
        self.DOTS_PER_MM = dpi/25.4
        self.DEBUG_EN = debug
        try:
            self.s.connect((self.HOST, self.PORT))
        except:
            print("Not connected")

    def __del__(self):
        self.s.close()

    def dbg_print(self, text):
        if self.DEBUG_EN:
            print(text)
    
    def SendToPrinter(self, cmd):
        if isinstance(cmd, str) :
            self.s.sendall(cmd.encode("latin_1"))
        elif isinstance(cmd, bytes):
            self.s.sendall(cmd)

    # all parameters in dots
    def LabelInit(self, height, width, gap):
        cmd = '\nOD\n'                  # Enable Direct Thermal Mode
        cmd += 'Q%s,%s\n'%(height, gap) # Set label height and gap width
        cmd += 'q%s\n'%width            # Set laben width
        self.SendToPrinter(cmd)

    # all parameters in mm
    def LabelInitMetric(self, height, width, gap):
        height = height * self.DOTS_PER_MM
        width  = width  * self.DOTS_PER_MM
        gap    = gap    * self.DOTS_PER_MM
        self.dbg_print('Height:%d Width: %d, Gap: %d\n'%(height,width,gap))
        self.LabelInit(height, width, gap)

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
        cmd = b"GW%d,%d,%d,%d,%s\n"%(x, y, width//8, height, data)
        self.AddToBuffer(cmd)
    
    # Print the Bitmap as ASCII Art
    def DbgPrintAsciiArt(self, data, width, out_filename):
        if self.DEBUG_EN:
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
        self.dbg_print(self.BUFFER)
        self.SendToPrinter(self.BUFFER)
    
    def AddToBuffer(self, cmd):
        if isinstance(cmd, str) :
            cmd = cmd.encode("latin_1")
        self.BUFFER = self.BUFFER + cmd
    
    def AddText(self, x, y, text, font=4, rot=0, reverse="N"):
        self.AddToBuffer("A%d,%d,%d,%d,%d,%d,%s,\"%s\"\n"%(x,y,rot,font,1,1,reverse,text))

    def AddQrCode(self, x, y, data, Scale=3, ErrCorLev="M"):
        self.AddToBuffer("b%d,%d,%s,%d,%d,%s,%s,%s,\"%s\"\n"%(x, y,"Q", 2, Scale, ErrCorLev, "A", "c", data))

# Main
# ------------------------------------------------------------------


if __name__ == '__main__':
    HOST = "zebra.lan"
    PORT = 9100

    p = Zebra(HOST, PORT)
    p.LabelInitMetric(25, 40, 2) # 25x40 mm wih 2 mm gap

    # use these handy functions ....
    # ------------------------------
    p.ClearBuffer()
    p.AddBitmap(0,   0,   "Tux.bmp")
    p.AddText  (0,   130, "FooBar")
    p.AddQrCode(120, 30,  123456)
    p.Print()

    # ... or do it like a pro :-)
    # ------------------------------
    label = """
N
A40,0,0,4,1,1,N, "123456789"
P1
"""
    p.SendToPrinter(label)
