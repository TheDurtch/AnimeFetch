# AnimeFetch

TO-DO: Make README more friendly 

This is my first time using Python and I am trying to learn while making this script

make sure to update the varibles in rss_feed.py before using

You'll need Aria2c (for rss-feed.py) and NvEnc (for encode_anime) to use these scripts.

The rss_feed.py script downloads any anime you add to rss.conf. rss.example.conf shows you how it should look like.

Right now only erai-raws and nyaa are supported and I don't plan on supporting others at the moment.

I have mine set to run every 15 mintes via cron

*/15 * * * * bash "/FULL/PATH/TO/rss_feed.sh" 2>&1 | grep -v "Torrent already downloaded" > ~/rss_feed.log
Feel free to change "rss_feed.example.sh" to suit your needs.


The encode_anime script watches a dirctory and when a file matching the config enter it get to work encoding using NvEnc (It's right now hardcoded to av1 encoding, I am thinking of added 2 modes tho, HEVC and AV1 mode)

The encpde.conf can be a bit daunting for some so let me explain it.

We have the following entry

"[SubsPlease] Re Zero kara Hajimeru Isekai Seikatsu:ReZero kara Hajimeru Isekai Seikatsu (2024) (a17947):-50"

"[SubsPlease] Re Zero kara Hajimeru Isekai Seikatsu" is the filename the script is going to look for. You just need to copy everything before the dash. (Full filename for reference [SubsPlease] Re Zero kara Hajimeru Isekai Seikatsu - 51v2 (1080p) [5DAFE728].mkv)

"ReZero kara Hajimeru Isekai Seikatsu (2024) (a17947)" I like to use Anidb names since I the send files to my plex server.

"-50" My biggest gripe with SubsPlease is there choice of how to number episodes. They never reset for the next season. You need to know how many empsodes you want to offset by and go back that many. (I really should have made this a positive number but I didn't and only have slight regret)
In therory it should work without it but I never tested it to I just add :0 to the end of everything.


There is a lot of info missing from here, I'll update this readme as I get a around to it
