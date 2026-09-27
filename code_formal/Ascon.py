def Ascon_Sbox():
    Sbox = []
    for X in range(32):
        x = [(X>>i)&1 for i in range(5)][::-1]; y = [0]*5; g = [0]*100; r = [0]*200; t = [0]*1000

        ################### Here is your code !! ###################
        DJ_master = [0]*80
        DJ_master[32] = x[4]
        DJ_master[33] = x[0] ^ DJ_master[32]
        DJ_master[34] = x[3]
        DJ_master[35] = x[4] ^ DJ_master[34]
        DJ_master[36] = x[1]
        DJ_master[37] = x[2] ^ DJ_master[36]
        DJ_master[38] = DJ_master[33]
        DJ_master[39] = x[1]
        DJ_master[40] = DJ_master[37]
        DJ_master[41] = x[3]
        DJ_master[42] = DJ_master[35]
        DJ_master[43] = 1 ^ DJ_master[38]
        DJ_master[44] = 1 ^ DJ_master[39]
        DJ_master[45] = 1 ^ DJ_master[40]
        DJ_master[46] = 1 ^ DJ_master[41]
        DJ_master[47] = 1 ^ DJ_master[42]
        DJ_master[48] = x[1]
        DJ_master[49] = DJ_master[43] & DJ_master[48]
        DJ_master[50] = DJ_master[37]
        DJ_master[51] = DJ_master[44] & DJ_master[50]
        DJ_master[52] = x[3]
        DJ_master[53] = DJ_master[45] & DJ_master[52]
        DJ_master[54] = DJ_master[35]
        DJ_master[55] = DJ_master[46] & DJ_master[54]
        DJ_master[56] = DJ_master[33]
        DJ_master[57] = DJ_master[47] & DJ_master[56]
        DJ_master[58] = DJ_master[51]
        DJ_master[59] = DJ_master[33] ^ DJ_master[58]
        DJ_master[60] = DJ_master[53]
        DJ_master[61] = x[1] ^ DJ_master[60]
        DJ_master[62] = DJ_master[55]
        DJ_master[63] = DJ_master[37] ^ DJ_master[62]
        DJ_master[64] = DJ_master[57]
        DJ_master[65] = x[3] ^ DJ_master[64]
        DJ_master[66] = DJ_master[49]
        DJ_master[67] = DJ_master[35] ^ DJ_master[66]
        DJ_master[68] = DJ_master[59]
        DJ_master[69] = DJ_master[61] ^ DJ_master[68]
        DJ_master[70] = DJ_master[67]
        DJ_master[71] = DJ_master[59] ^ DJ_master[70]
        DJ_master[72] = DJ_master[63]
        DJ_master[73] = DJ_master[65] ^ DJ_master[72]
        DJ_master[74] = 1 ^ DJ_master[63]
        DJ_master[75] = DJ_master[71]
        y[0] = DJ_master[75]
        DJ_master[76] = DJ_master[69]
        y[1] = DJ_master[76]
        DJ_master[77] = DJ_master[74]
        y[2] = DJ_master[77]
        DJ_master[78] = DJ_master[73]
        y[3] = DJ_master[78]
        DJ_master[79] = DJ_master[67]
        y[4] = DJ_master[79]
        ################### Here is your code !! ###################


        Y = (y[0]<<4)|(y[1]<<3)|(y[2]<<2)|(y[3]<<1)|(y[4]<<0)
        
        Sbox.append(Y)
    return Sbox
if __name__ == "__main__":
    Sbox = Ascon_Sbox()
    
    Ascon_original = [4,0xb,0x1f,0x14,0x1a,0x15,0x9,0x2,0x1b,0x5,0x8,0x12,0x1d,0x3,0x6,0x1c,0x1e,0x13,0x7,0xe,0x0,0xd,0x11,0x18,0x10,0xc,0x1,0x19,0x16,0xa,0xf,0x17]
    if tuple(Sbox) != tuple(Ascon_original):
        print('Wrong!!')
        for i in range(len(Sbox)):
            if Sbox[i] != Ascon_original[i]:
                print(f'{i:2X}th value : {Sbox[i]:5b}({Sbox[i]:2X}) {Ascon_original[i]:5b}({Ascon_original[i]:2X})')
    else:
        print('Right!!')
    