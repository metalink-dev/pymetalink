SET PYTHONDIR=c:\Python27

SET BUILDS=..\builds
FOR /F "TOKENS=1,2 DELIMS=/ " %%A IN ('DATE /T') DO SET mm=%%B
FOR /F "TOKENS=2,3 DELIMS=/ " %%A IN ('DATE /T') DO SET dd=%%B
FOR /F "TOKENS=3,4 DELIMS=/ " %%A IN ('DATE /T') DO SET yyyy=%%B

SET DATE=%yyyy%-%mm%-%dd%