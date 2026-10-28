"""Alternating weighted binary treemap; geometry only, no KPI formulas."""
from decimal import Decimal,localcontext


def treemap_rectangles(items):
    items=list(items)
    positive=[(identifier,Decimal(weight)) for identifier,weight in items if weight>0]
    if any(Decimal(weight)<0 for _,weight in items):raise ValueError('Treemap tidak mendukung bobot negatif.')
    rectangles=[]
    def split(rows,x,y,w,h,axis):
        if len(rows)==1:
            rectangles.append(dict(id=rows[0][0],x=x,y=y,width=w,height=h))
            return
        total=sum((row[1] for row in rows),Decimal(0))
        prefix=[];current=Decimal(0)
        for _,weight in rows[:-1]:current+=weight;prefix.append(current)
        index=min(range(len(prefix)),key=lambda i:abs(prefix[i]-total/2))+1
        ratio=prefix[index-1]/total
        if axis==0:
            cut=w*ratio
            split(rows[:index],x,y,cut,h,1);split(rows[index:],x+cut,y,w-cut,h,1)
        else:
            cut=h*ratio
            split(rows[:index],x,y,w,cut,0);split(rows[index:],x,y+cut,w,h-cut,0)
    if positive:
        with localcontext() as context:
            context.prec=50
            split(positive,Decimal(0),Decimal(0),Decimal(1),Decimal(1),0)
    return rectangles
