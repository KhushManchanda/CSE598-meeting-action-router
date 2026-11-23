"""ASU-style poster layout. Shared drawing functions are in build_poster.py."""

maroon = '#8C1D40'
gold = '#FFC627'
gray = '#333333'
pink = '#F8EFF2'
border = '#D7B9C3'
navy = '#191919'
teal = maroon

def centered(x, y, width, text, size, font='Bold', color=navy):
    length = pdfmetrics.stringWidth(text, font, size)
    assert length <= width, (text, length, width)
    txt(x+(width-length)/2, y, text, size, font, color)

def panel(x, y, width, height, title):
    rect(x,y,width,height,white,maroon,7)
    rect(x,y,width,64,maroon)
    txt(x+22,y+16,title,34,'Bold',white)

def detail(x, y, width, label, body, size=28, limit=140):
    txt(x,y,label,30,'Bold',maroon)
    return para(x,y+41,width,body,size,gray,maxh=limit)

rect(0,0,W,H,white)
rect(58,54,1612,12,gold)
rect(58,96,221,200,pink,border)
centered(58,126,221,'GROUP',27,color=maroon)
centered(58,173,221,'30',86,color=maroon)
centered(307,100,1363,'Meeting Action-Item Router',78,color=maroon)
centered(307,207,1363,'From meeting notes to assigned, verified actions',33)
centered(307,266,1363,'Arjun Ranjan   |   Khush Manchanda',29)
centered(307,310,1363,'Project stakeholder   Neha Kashyap',26,font='Regular')
txt(58,333,'CSE 598 AGENTIC AI',24,'Bold',maroon)

panel(58,390,1612,401,'PROJECT WORKFLOW')
items = [
    ('Input','Add a transcript, date, and participant roster.'),
    ('Extract','Find commitments and quote the source turns.'),
    ('Resolve','Map the owner, due date, and destination.'),
    ('Review','Check the evidence. Approve, edit, or reject.'),
    ('Act','Create a card, event, or Gmail draft.'),
    ('Verify','Read back the result and flag issues.'),
]
for i,(title, body) in enumerate(items):
    x=79+264*i
    rect(x,480,244,238,pink,border,8)
    rect(x+14,493,48,48,gold,None,24)
    centered(x+14,505,48,str(i+1),27,color=navy)
    txt(x+15,556,title,32,'Bold',maroon)
    para(x+15,603,213,body,24,gray,maxh=107)
    if i<5:
        c.setFillColor(HexColor(gold))
        a=c.beginPath()
        a.moveTo(x+246,H-590); a.lineTo(x+263,H-601); a.lineTo(x+246,H-612); a.close()
        c.drawPath(a,fill=1,stroke=0)
para(82,738,1540,'One agent handles each action through extraction, resolution, validation, approval, execution, and verification.',26,gray,maxh=40)

panel(58,819,785,697,'PROJECT OVERVIEW')
detail(82,906,737,'The problem','People leave meetings with commitments spread across the transcript. Someone still has to find each task, identify its owner, and enter it in the right tool.')
detail(82,1085,737,'What we built','A Streamlit review workspace backed by an OpenAI model and Composio integrations for Trello, Google Calendar, and Gmail drafts.')
detail(82,1260,737,'Why the agent checks its work','Roster and evidence checks catch unsupported proposals before review. A SQLite ledger and JSON report record what happened. Unresolved actions stay visible for follow-up.')

panel(865,819,805,697,'REVIEWING A REAL UI RUN')
x, y, width = 887, 908, 761
c.drawImage(ImageReader(str(base/'screenshots/02_action_evidence.jpg')),x,H-y-width*720/1280,width=width,height=width*720/1280)
para(x,1356,width,'Offline walkthrough. Dana’s note names Omar and gives a deadline. The reviewer edited the title and approved the simulated Trello card. The returned card matched the approved fields.',27,gray,maxh=143)

panel(58,1545,785,762,'MILESTONE 2 RESULTS')
para(82,1631,737,'We evaluated 16 transcripts with 51 reference actions. The table shows pooled recall for synthetic and AMI meetings.',28,gray,maxh=100)
rect(82,1752,737,52,pink)
for x,label in [(98,'System'),(390,'Synthetic'),(629,'AMI')]:
    txt(x,1764,label,25,'Bold',maroon)
with (base/'milestone2_results.csv').open(newline='') as f:
    result_rows=list(csv.DictReader(f))
for i,(key,label) in enumerate([('b0','B0  Keyword rules'),('b1','B1  One model call'),('a','Agent A')]):
    y=1820+58*i
    txt(98,y,label,25,'Bold' if key=='a' else 'Regular')
    for x,dataset in [(390,'synthetic'),(629,'ami')]:
        rr=[r for r in result_rows if (r['system'],r['dataset'])==(key,dataset)]
        matches=sum(round(float(r['recall'] or 0)*int(r['n_gold'])) for r in rr)
        total=sum(int(r['n_gold']) for r in rr)
        txt(x,y,f'{matches/total:.1%}',26,'Bold' if key=='a' else 'Regular')
    rule(91,y+42,718,border)
para(82,2011,737,'Agent A matched 9/23 synthetic and 4/22 AMI actions. Owner labels were correct on those matches. Agent A is scored on verified outputs, so escalations can count as misses.',27,gray,maxh=137)
para(82,2162,737,'Live CLI checks created a Trello card, Calendar event, and Gmail draft. Calendar read-back was verified separately after a parsing fix.',26,gray,maxh=122)

panel(865,1545,805,762,'PRODUCT EXPERIENCE')
detail(890,1635,754,'Review and route actions','Open a proposal beside its transcript evidence. Edit, reject, or approve it for Trello, Calendar, or Gmail.')
detail(890,1814,754,'Find approved cards in one place','See verified Trello cards and actions that need follow-up. Open linked cards from the action ledger.')
detail(890,1990,754,'Review changes before a retry','Return to review when a repair changes the assignee, recipient, due date, or other material details.')
para(890,2155,748,'Use the run report to check what was verified, rejected, or flagged for follow-up.',26,gray,maxh=100)

rect(58,2351,1612,8,gold)
txt(58,2392,'Arizona State University',44,'Bold',maroon)
txt(58,2452,'Ira A. Fulton Schools of Engineering',31,'Bold',navy)
txt(58,2500,'CSE 598 Agentic AI   |   Group 30',24,'Regular',gray)
txt(1002,2401,'PROJECT REPOSITORY',24,'Bold',maroon)
txt(1002,2441,'github.com/KhushManchanda/',23,'Regular',gray)
txt(1002,2472,'CSE598-meeting-action-router',23,'Regular',gray)
txt(1002,2505,'Milestone 2 reference commit  e54e61a',22,'Regular',gray)
c.linkURL('https://github.com/KhushManchanda/CSE598-meeting-action-router',(995,H-2500,1500,H-2435),relative=0)
