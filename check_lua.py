"""Checa a sintaxe dos .lua/.dlua do plugin usando a lua54 do proprio Firecast (so compila, nao executa)."""
import ctypes, glob, os, sys

lua = ctypes.CDLL(os.path.join(os.environ["LOCALAPPDATA"], "Firecast", "lua54x64.dll"))
lua.luaL_newstate.restype = ctypes.c_void_p
lua.luaL_loadbufferx.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_char_p]
lua.lua_tolstring.restype = ctypes.c_char_p
lua.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
L = lua.luaL_newstate()
ruins = 0
for f in sorted(glob.glob("plugin/**/*.lua", recursive=True) + glob.glob("plugin/**/*.dlua", recursive=True)):
    src = open(f, "rb").read()
    if lua.luaL_loadbufferx(L, src, len(src), ("@" + f).encode(), b"t") != 0:
        print("ERRO", lua.lua_tolstring(L, -1, None).decode("utf-8", "replace"))
        ruins += 1
    lua.lua_settop.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lua.lua_settop(L, 0)
print("ok" if ruins == 0 else f"{ruins} arquivo(s) com erro")
sys.exit(1 if ruins else 0)
