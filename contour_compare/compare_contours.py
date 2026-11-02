#!/usr/bin/env python3
"""Compare all black stroke boundaries with their one-pixel centerlines (CPU only)."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw

DIRECTIONS = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]

def skeleton_strokes(binary):
    if hasattr(cv2, "ximgproc") and hasattr(cv2.ximgproc, "thinning"):
        thin = cv2.ximgproc.thinning(binary, thinningType=cv2.ximgproc.THINNING_ZHANGSUEN)
    else:
        from skimage.morphology import skeletonize
        thin = (skeletonize(binary > 0).astype(np.uint8) * 255)
    on = set(map(tuple, np.argwhere(thin > 0)))
    # suppress redundant 8-connected diagonal edges if the two pixels already share an orthogonal neighbor
    def adjacent(p):
        y, x = p
        result=[]
        for dy,dx in DIRECTIONS:
            q=(y+dy,x+dx)
            if q not in on:
                continue
            if dy and dx and ((y+dy,x) in on or (y,x+dx) in on):
                continue
            result.append(q)
        return result
    neighbors={p:adjacent(p) for p in on}
    junctions={p for p,n in neighbors.items() if len(n)!=2}
    edges=set()
    def key(p,q):return (p,q) if p<q else (q,p)
    traces=[]
    for start in sorted(junctions):
        for dest in neighbors[start]:
            if key(start,dest) in edges: continue
            line=[start,dest];edges.add(key(start,dest));prev=start;cur=dest
            while cur not in junctions:
                nxt=[q for q in neighbors[cur] if q!=prev and key(cur,q) not in edges]
                if not nxt:break
                q=nxt[0];edges.add(key(cur,q));line.append(q);prev,cur=cur,q
            traces.append(line)
    for start in sorted(on):
        for dest in neighbors[start]:
            if key(start,dest) in edges:continue
            line=[start,dest];edges.add(key(start,dest));prev=start;cur=dest
            while True:
                nxt=[q for q in neighbors[cur] if q!=prev and key(cur,q) not in edges]
                if not nxt:break
                q=nxt[0];edges.add(key(cur,q));line.append(q);prev,cur=cur,q
                if cur==start:break
            traces.append(line)
    return thin, traces

def contour_strokes(binary):
    contours,_=cv2.findContours(binary,cv2.RETR_LIST,cv2.CHAIN_APPROX_NONE)
    return [[(int(p[0][1]),int(p[0][0])) for p in contour] for contour in contours]

def polyline_length(points):
    return sum(((b[0]-a[0])**2+(b[1]-a[1])**2)**.5 for a,b in zip(points,points[1:]))

def simplify(lines, min_length, epsilon):
    out=[]
    for line in lines:
        if len(line)<2 or polyline_length(line)<min_length:continue
        xy=np.asarray([(x,y) for y,x in line],dtype=np.float32).reshape(-1,1,2)
        approx=cv2.approxPolyDP(xy,epsilon,False).reshape(-1,2)
        if len(approx)>1:out.append([(int(y),int(x)) for x,y in approx])
    return out

def render_strokes(lines, size):
    w,h=size
    canvas=np.full((h,w,3),255,dtype=np.uint8)
    for line in lines:
        pts=np.asarray([(x,y) for y,x in line],dtype=np.int32).reshape(-1,1,2)
        if len(pts)>1:cv2.polylines(canvas,[pts],False,(0,0,0),1,lineType=cv2.LINE_AA)
    return Image.fromarray(canvas)

def metrics(lines):
    return {'stroke_count':len(lines),'waypoint_count':sum(len(x) for x in lines),
            'draw_length_px':round(sum(polyline_length(x) for x in lines),2)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',required=True)
    ap.add_argument('--output',required=True)
    ap.add_argument('--threshold',type=int,default=125)
    ap.add_argument('--min-length',type=float,default=10)
    ap.add_argument('--epsilon',type=float,default=1.5)
    args=ap.parse_args()
    if not 0<args.threshold<255:ap.error('threshold must be 1..254')
    src=Path(args.input);out=Path(args.output)
    if not src.is_file():ap.error(f'Image not found: {src}')
    out.mkdir(parents=True,exist_ok=True)
    orig=Image.open(src).convert('RGB');rgb=np.asarray(orig)
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    binary=cv2.threshold(gray,args.threshold,255,cv2.THRESH_BINARY_INV)[1]
    # Ignore tiny stray patches without forcing connections between separate details.
    count,labeled,stats,_=cv2.connectedComponentsWithStats(binary,8)
    clean=np.zeros_like(binary)
    for i in range(1,count):
        if stats[i,cv2.CC_STAT_AREA]>=12:clean[labeled==i]=255
    boundary=contour_strokes(clean)
    thin,center=skeleton_strokes(clean)
    outer=simplify(boundary,args.min_length,args.epsilon)
    center=simplify(center,args.min_length,args.epsilon)
    im_outer=render_strokes(outer,orig.size)
    im_center=render_strokes(center,orig.size)
    orig.save(out/'input.png')
    Image.fromarray(255-clean).save(out/'binary.png')
    Image.fromarray(255-thin).save(out/'skeleton_raw.png')
    im_outer.save(out/'outer_contour.png')
    im_center.save(out/'centerline.png')
    header=44; w,h=orig.size
    sheet=Image.new('RGB',(3*w,h+header),'white');d=ImageDraw.Draw(sheet)
    for idx,(label,im) in enumerate([('INPUT',orig),('BOUNDARIES',im_outer),('CENTERLINES',im_center)]):
        sheet.paste(im,(idx*w,header));d.text((idx*w+12,14),label,fill='black')
    sheet.save(out/'comparison.png')
    report={'input':str(src),'image_size':[w,h],'threshold':args.threshold,
            'min_stroke_length_px':args.min_length,'polyline_epsilon_px':args.epsilon,
            'boundary_contours':metrics(outer),'centerline_strokes':metrics(center),
            'note':'Contours include inner and outer edges of thick black lines; stroke counts depend on threshold and pruning. No turtlesim timing inferred.'}
    (out/'metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('OUTER',json.dumps(report['boundary_contours']),flush=True)
    print('CENTER',json.dumps(report['centerline_strokes']),flush=True)
    print('RESULT_DIR:',out,flush=True)
    print('STATUS: PASS',flush=True)

if __name__=='__main__':main()
