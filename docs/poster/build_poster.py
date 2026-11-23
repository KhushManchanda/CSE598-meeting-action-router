from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
import argparse
import csv
from reportlab import __file__ as reportlab_path
from reportlab.lib.utils import ImageReader
from collections import defaultdict

base = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description="Build the Group 30 print poster.")
parser.add_argument("style", choices=("asu", "editorial"))
parser.add_argument("--output", type=Path)
args = parser.parse_args()
out = args.output or base / ("Group30_Poster_ASU.pdf" if args.style == "asu" else "Group30_Poster_Editorial.pdf")
out.parent.mkdir(parents=True, exist_ok=True)
system_fonts = Path("/System/Library/Fonts/Supplemental")
fallback = Path(reportlab_path).parent / "fonts"
for name, mac, portable in [
    ("Regular", "Arial.ttf", "Vera.ttf"),
    ("Bold", "Arial Bold.ttf", "VeraBd.ttf"),
    ("Display", "Georgia Bold.ttf", "VeraBd.ttf"),
]:
    font = system_fonts / mac
    pdfmetrics.registerFont(TTFont(name, str(font if font.is_file() else fallback / portable)))

W,H = 1728,2592
c = canvas.Canvas(str(out),pagesize=(W,H), pageCompression=1, initialFontName="Regular")
c.setTitle('Meeting Action-Item Router | Group 30')
c.setAuthor('Arjun Ranjan and Khush Manchanda')
navy='#12282D'; teal='#12695E'; white='#FFFFFF'; paper='#F8F7F2'; muted='#425B5B'
line='#CEDBD3'; pale='#EAF2EC'; lime='#D8F08A'
def rect(x,y,w,h,fill,stroke=None,r=0):
    c.setFillColor(HexColor(fill))
    if stroke: c.setStrokeColor(HexColor(stroke))
    if r: c.roundRect(x,H-y-h,w,h,r,fill=1,stroke=bool(stroke))
    else: c.rect(x,H-y-h,w,h,fill=1,stroke=bool(stroke))
def txt(x,y,s,n=28,font='Regular',color=navy):
    c.setFont(font,n); c.setFillColor(HexColor(color))
    c.drawString(x,H-y-n*.8,s)
def para(x,y,w,s,n=30,color=navy,font='Regular',leading=None,maxh=None):
    p=Paragraph(s,ParagraphStyle('poster',fontName=font,fontSize=n,leading=leading or n*1.23,textColor=HexColor(color)))
    _,height=p.wrap(w,H)
    if maxh: assert height<=maxh,(s,height,maxh)
    p.drawOn(c,x,H-y-height)
    return height
def rule(x,y,w,color=line):
    c.setStrokeColor(HexColor(color));c.setLineWidth(1.5)
    c.line(x,H-y,x+w,H-y)
def heading(x,y,s):
    txt(x,y,s,46,'Bold')
def arrow(x,y):
    c.setStrokeColor(HexColor(teal)); c.setLineWidth(3)
    path=c.beginPath()
    path.moveTo(x,H-y); path.lineTo(x+28,H-y)
    path.moveTo(x+19,H-y+8); path.lineTo(x+28,H-y); path.lineTo(x+19,H-y-8)
    c.drawPath(path)
def field(x,y,label,value):
    txt(x,y,label,21,'Bold',teal)
    txt(x,y+31,value,30,'Bold')

if args.style == "asu":
    exec(compile((base / "asu_layout.py").read_text(), "asu_layout.py", "exec"))
    c.showPage()
    c.save()
    raise SystemExit

rect(0,0,W,H,paper)
rect(0,0,W,503,navy)
rect(64,66,54,6,lime)
txt(135,56,'CSE 598 AGENTIC AI   /   GROUP 30',24,'Bold',lime)
txt(64,121,'Meeting Action-Item',103,'Display',white)
txt(64,237,'Router',103,'Display',white)
para(65,352,1450,'Turn meeting commitments into assigned tasks, calendar events, and email drafts with a human review step.',38,white,maxh=100)
txt(65,454,'ARJUN RANJAN  +  KHUSH MANCHANDA',24,'Bold',lime)

heading(64,548,'From meeting notes to verified actions')
para(66,609,1520,'Input a speaker-labeled transcript, the meeting date, and a participant roster. Each proposed action carries evidence from the conversation.',30,muted,maxh=88)
steps=[
    ('Extract','Find commitments and cite the source turns.'),
    ('Resolve','Look up the owner, date, and destination.'),
    ('Review','Check evidence, then approve, edit, or reject.'),
    ('Execute','Create the approved card, event, or draft.'),
    ('Verify','Read it back and flag anything that needs follow-up.'),
]
for i,(a,b) in enumerate(steps):
    x=64+327*i
    rect(x,711,292,188,white,line,12)
    txt(x+19,732,a,36,'Bold',teal)
    para(x+19,786,254,b,27,maxh=104)
    if i<4: arrow(x+297,800)
txt(65,921,'If details are unclear, the agent can revise its proposal or flag it for follow-up.',27,'Regular',muted)

heading(64,990,'One commitment, from transcript to Trello')
rect(64,1061,1600,394,pale,None,16)
txt(93,1091,'SOURCE TRANSCRIPT',23,'Bold',teal)
para(93,1142,626,'“Omar will prepare the deployment checklist by November 6, 2026.”',42,navy,'Display',maxh=180)
txt(94,1313,'Dana, weekly project sync',27,'Regular',muted)
arrow(722,1238)
rect(775,1084,864,348,white,None,11)
txt(801,1109,'REVIEWED ACTION',23,'Bold',teal)
para(802,1154,790,'Prepare the reviewed deployment checklist',38,navy,'Bold',maxh=95)
field(802,1267,'ASSIGNEE','Omar')
field(1070,1267,'DUE DATE','Nov. 6, 2026')
field(1370,1267,'DESTINATION','Trello')
rule(802,1341,810)
para(802,1360,802,'Title edited and approved. The returned mock card matched the approved fields.',25,muted,maxh=65)
txt(65,1474,'Offline UI walkthrough with fictional participants and simulated tools.',25,'Regular',muted)

heading(64,1550,'What we measured')
heading(1120,1550,'Product workflow')
para(65,1610,1000,'16 transcripts, 51 reference actions. We compared Agent A with keyword rules (B0) and a single model call (B1).',28,muted,maxh=78)
rect(64,1710,1002,482,white,line,12)
txt(87,1735,'Action recall',32,'Bold')
txt(87,1780,'Share of reference actions matched, pooled by dataset',23,'Regular',muted)
with (base / 'milestone2_results.csv').open(newline='') as f:
    groups=defaultdict(list)
    for row in csv.DictReader(f): groups[row['dataset'],row['system']].append(row)
for j,(ds,label) in enumerate([('synthetic','Synthetic  /  23 actions'),('ami','AMI meetings  /  22 actions')]):
    yy=1835+165*j
    txt(87,yy,label,24,'Bold')
    for i,(key,tag,col) in enumerate([('b0','B0','#899D98'),('b1','B1','#375D74'),('a','Agent A',teal)]):
        y=yy+34+38*i
        rs=groups[ds,key]
        num=sum(round(float(r['recall'] or 0)*int(r['n_gold'])) for r in rs)
        den=sum(int(r['n_gold']) for r in rs)
        pct=num/den
        txt(88,y,tag,22,'Bold' if key=='a' else 'Regular')
        rect(208,y+4,658,20,'#EDF2EF',None,4)
        rect(208,y+4,658*pct,20,col,None,4)
        txt(884,y,f'{pct:.1%}',24,'Bold',navy)
para(64,2218,1002,'Agent A matched 9 of 23 synthetic actions and 4 of 22 AMI actions. Owner labels were correct on those matches. Escalated items can count as misses because Agent A is scored on verified outputs.',28,maxh=147)

for y,(title,body) in zip((1621,1761,1901),[
    ('Trello','Assign tasks with due dates and find approved cards in one view.'),
    ('Calendar','Create an event with the reviewed date and attendees.'),
    ('Gmail','Save a draft with the reviewed recipient, subject, and message.'),
]):
    txt(1120,y,title,31,'Bold',teal)
    para(1120,y+43,543,body,27,maxh=102)
txt(1120,2050,'Approval and follow-up',31,'Bold',teal)
para(1120,2099,543,'Review material changes before a retry. The ledger shows verified actions and anything that needs follow-up.',27,maxh=165)

rect(0,2390,W,202,navy)
txt(65,2418,'CSE 598 FINAL PROJECT  /  GROUP 30',27,'Bold',lime)
txt(65,2460,'Milestone 2 deployment report  /  Evaluation at GitHub commit e54e61a',23,'Regular',white)
url='https://github.com/KhushManchanda/CSE598-meeting-action-router'
txt(65,2502,'github.com/KhushManchanda/CSE598-meeting-action-router',23,'Regular',white)
c.linkURL(url,(64,H-2536,840,H-2497),relative=0)
c.showPage()
c.save()
