"""Roda os modulos do plugin na lua54 do Firecast com o SDK simulado: executa os asserts de cada arquivo."""
import ctypes, os, sys

lua = ctypes.CDLL(os.path.join(os.environ["LOCALAPPDATA"], "Firecast", "lua54x64.dll"))
lua.luaL_newstate.restype = ctypes.c_void_p
for f, a in [("luaL_openlibs", [ctypes.c_void_p]),
             ("luaL_loadbufferx", [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_char_p]),
             ("lua_pcallk", [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ssize_t, ctypes.c_void_p]),
             ("lua_tolstring", [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p])]:
    getattr(lua, f).argtypes = a
lua.lua_tolstring.restype = ctypes.c_char_p

STUB = b"""
NDB = {load = function() return {} end}
Firecast = {Messaging = {listen = function() end}}
Internet = {httpEncode = function(s) return s end}
local real = require
require = function(n) if n == "ui.dlua" then return {novo = function() end} end return {} end
"""
for nome in ("previa.dlua", "turno.dlua"):
    L = lua.luaL_newstate()
    lua.luaL_openlibs(L)
    src = STUB + open("plugin/" + nome, "rb").read()
    r = lua.luaL_loadbufferx(L, src, len(src), ("@" + nome).encode(), b"t") or lua.lua_pcallk(L, 0, 0, 0, 0, None)
    if r != 0:
        sys.exit("FALHOU: " + lua.lua_tolstring(L, -1, None).decode("utf-8", "replace"))
    print("ok", nome)

# ui.escrever com o arquivo preso (ajudante ou antivirus lendo, como no PC de um jogador): devolve false, sem erro
TESTE_UI = b"""
local preso = false
VHD = {fileExists = function() return true end,
       deleteFile = function() if preso then error("Acesso negado [piscar.txt]") end end,
       openFile = function() return {write = function() end, close = function() end} end}
require = function(n) if n == "utils.lua" then return {binaryEncode = function(b, _, t) return #t end} end return {} end
local ui = load(UI_SRC, "@ui.dlua")()
assert(ui.escrever("piscar.txt", "1") == true)
preso = true
assert(ui.escrever("piscar.txt", "1") == false)
"""
L = lua.luaL_newstate()
lua.luaL_openlibs(L)
src = b"UI_SRC = [==[" + open("plugin/ui.dlua", "rb").read() + b"]==]\n" + TESTE_UI
r = lua.luaL_loadbufferx(L, src, len(src), b"@teste_ui", b"t") or lua.lua_pcallk(L, 0, 0, 0, 0, None)
if r != 0:
    sys.exit("FALHOU: " + lua.lua_tolstring(L, -1, None).decode("utf-8", "replace"))
print("ok ui.dlua")
