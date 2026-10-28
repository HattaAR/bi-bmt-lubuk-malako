"""Illustrative monthly principal split; no margin, model or contract updates."""
from calendar import monthrange
from datetime import date,datetime
from decimal import Decimal,ROUND_DOWN,localcontext

MAX_MONTHS=36 # UI facility only, not an approved contractual tenor.


def monthly_date(start,offset):
    month_index=start.year*12+start.month-1+offset
    year,month=divmod(month_index,12);month+=1
    if year>9999:raise ValueError('Jadwal melewati rentang tanggal yang didukung.')
    end=monthrange(year,month)[1]
    day=end if start.day==monthrange(start.year,start.month)[1] else min(start.day,end)
    return date(year,month,day)


def simulate_principal(outstanding,months,start_date):
    if not isinstance(outstanding,Decimal) or not outstanding.is_finite() or outstanding<0:raise ValueError('Outstanding pokok harus Decimal yang valid dan tidak negatif.')
    if outstanding>=Decimal('1e16'):raise ValueError('Outstanding melewati rentang nominal data mart.')
    if isinstance(months,bool) or not isinstance(months,int) or not 1<=months<=MAX_MONTHS:raise ValueError('Jumlah bulan harus bilangan bulat 1–36.')
    if not isinstance(start_date,date) or isinstance(start_date,datetime):raise ValueError('Isi tanggal pembayaran skenario pertama.')
    with localcontext() as context:
        context.prec=50
        if outstanding!=outstanding.quantize(Decimal('.01')):raise ValueError('Outstanding harus memiliki paling banyak dua desimal.')
        mean=outstanding/months;regular=mean.quantize(Decimal('.01'),rounding=ROUND_DOWN)
        balance=outstanding;schedule=[]
        for index in range(months):
            amount=balance if index==months-1 else regular
            balance-=amount
            schedule.append(dict(period=index+1,date=monthly_date(start_date,index),principal=amount,balance=balance))
        return dict(principal=outstanding,months=months,start_date=start_date,regular_principal=regular,
                    mean_principal=mean,last_principal=schedule[-1]['principal'],total_principal=outstanding,
                    schedule=schedule,status='zero_outstanding' if outstanding==0 else 'available')


def compare_scenarios(outstanding,months,start_date):
    options=[simulate_principal(outstanding,n,start_date) for n in sorted({6,12,18,months})]
    with localcontext() as context:
        context.prec=50
        maximum=max(r['mean_principal'] for r in options)
        return [dict(months=r['months'],regular_principal=r['regular_principal'],last_principal=r['last_principal'],
                     total_principal=r['total_principal'],selected=r['months']==months,
                     relative_percent=r['mean_principal']/maximum*100 if maximum else None) for r in options]
