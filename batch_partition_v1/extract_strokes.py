import argparse,sys,json,math
from pathlib import Path
import cv2,numpy as np
sys.path.insert(0,'/contour_code')
from compare_contours import skeleton_strokes,simplify
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out',required=True);p.add_argument('--subject',required=True);a=p.parse_args()
im=cv2.imread(a.input);assert im is not None and im.shape[:2]==(512,512)
gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY);binary=cv2.threshold(gray,125,255,cv2.THRESH_BINARY_INV)[1]
n,labels,stats,_=cv2.connectedComponentsWithStats(binary,8);clean=np.zeros_like(binary)
for i in range(1,n):
 if stats[i,cv2.CC_STAT_AREA]>=12:clean[labels==i]=255
_,lines=skeleton_strokes(clean);lines=simplify(lines,10,1.5)
strokes=[]
for i,line in enumerate(lines,1):
 xy=[[round(.7+x*9.6/511,5),round(10.3-y*9.6/511,5)] for y,x in line]
 if len(xy)>1:strokes.append({'id':f'{a.subject}_{i:04d}','points':xy})
assert 4<=len(strokes)<=500,f'{a.subject}: unreasonable strokes {len(strokes)}; inspect image manually'
out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps({'subject':a.subject,'source_image':a.input,'strokes':strokes},indent=2))
print('EXTRACT PASS',a.subject,len(strokes),'strokes',sum(len(s['points']) for s in strokes),'waypoints',flush=True)
