#!/usr/bin/env python3
"""MSOS Billing Pro Enterprise.

Offline-first PySide6 billing and invoice management system with SQLite storage,
customer/service/company/template management, high quality PDF/image invoice exports,
Google Drive upload queue metadata, audit logging, and a drag/drop template designer.
"""
from __future__ import annotations

import base64, datetime as dt, hashlib, hmac, importlib.util, json, os, secrets, sqlite3, sys, uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

APP_NAME="MSOS BILLING PRO ENTERPRISE"; APP_SLUG="msos_billing_pro_enterprise"; VERSION="1.0.0"
REQUIRED={"PySide6":"PySide6","reportlab":"reportlab","fitz":"PyMuPDF","PIL":"Pillow","cv2":"opencv-python","qrcode":"qrcode","barcode":"python-barcode","pandas":"pandas","openpyxl":"openpyxl","cryptography":"cryptography","requests":"requests","matplotlib":"matplotlib","dotenv":"python-dotenv","sqlalchemy":"SQLAlchemy","googleapiclient":"google-api-python-client","google_auth_oauthlib":"google-auth-oauthlib"}

def missing_packages()->list[str]:
    return [pkg for mod,pkg in REQUIRED.items() if importlib.util.find_spec(mod) is None]

def data_dir()->Path:
    base=Path(os.environ.get("PROGRAMDATA",Path.home()/"AppData"/"Local")) if os.name=="nt" else Path(os.environ.get("XDG_DATA_HOME",Path.home()/".local"/"share"))
    p=base/APP_SLUG; p.mkdir(parents=True,exist_ok=True); return p
DATA=data_dir(); DB=DATA/"billing.sqlite3"; OUT=DATA/"Bills"; ASSETS=DATA/"assets"; BACKUPS=DATA/"backups"
for p in (OUT,ASSETS,BACKUPS): p.mkdir(parents=True,exist_ok=True)

def now(): return dt.datetime.now().isoformat(timespec="seconds")
def money(v:float)->str: return f"₹{v:,.2f}"
def hash_password(password:str,salt:str|None=None)->str:
    salt=salt or secrets.token_hex(16); digest=hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),200_000).hex(); return f"{salt}${digest}"
def verify_password(password:str, stored:str)->bool:
    salt,digest=stored.split("$",1); return hmac.compare_digest(hash_password(password,salt).split("$",1)[1],digest)

class Store:
    def __init__(self,path:Path=DB): self.path=path; self.init()
    def con(self):
        c=sqlite3.connect(self.path); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c
    def init(self):
        with self.con() as c:
            c.executescript(SCHEMA)
            if not c.execute("select id from users limit 1").fetchone():
                c.execute("insert into users(username,password_hash,role,pin_hash,active) values(?,?,?,?,1)",("admin",hash_password("admin123"),"Super Admin",hash_password("1234")))
                cid=c.execute("insert into companies(name,branch,address,phone,email,gstin,pan,invoice_prefix,invoice_suffix,footer,terms,active) values(?,?,?,?,?,?,?,?,?,?,?,1)",("MSOS","Main Branch","Your business address","9999999999","admin@example.com","","","MSOS-","","Thank you for your business","Goods/services once billed are governed by company policy.")).lastrowid
                for name,price,gst in [("PAN Card Service",150,18),("Aadhaar Update",100,18),("Online Application",80,0)]: c.execute("insert into services(name,category,code,cost_price,selling_price,gst,discount,active,display_order) values(?,?,?,?,?,?,?,?,?)",(name,"Digital Services",name[:3].upper(),0,price,gst,0,1,1))
                layout=json.dumps(DEFAULT_LAYOUT); c.execute("insert into templates(name,category,paper,orientation,layout_json,builtin,active) values(?,?,?,?,?,?,1)",("Modern Blue A4","Built-in","A4","Portrait",layout,1))
    def q(self,sql:str,args:tuple=()):
        with self.con() as c: return c.execute(sql,args).fetchall()
    def one(self,sql:str,args:tuple=()):
        with self.con() as c: return c.execute(sql,args).fetchone()
    def run(self,sql:str,args:tuple=()):
        with self.con() as c:
            cur=c.execute(sql,args); return cur.lastrowid
    def audit(self,user:str,action:str,entity:str,entity_id:str,details:dict[str,Any]|None=None): self.run("insert into audit_logs(ts,username,action,entity,entity_id,details) values(?,?,?,?,?,?)",(now(),user,action,entity,entity_id,json.dumps(details or {})))

SCHEMA=r'''
create table if not exists users(id integer primary key, username text unique not null, password_hash text not null, role text not null check(role in('Super Admin','Admin','Operator','Viewer')), pin_hash text, remember_token text, active integer default 1, created_at text default current_timestamp);
create table if not exists customers(id integer primary key, customer_id text unique, photo_path text, name text not null, father_name text, mother_name text, mobile text, alt_mobile text, email text, address text, city text, state text, country text default 'India', pin_code text, gst_number text, pan_number text, aadhaar_number text, qr_path text, notes text, tags text, outstanding_balance real default 0, documents_json text default '[]', active integer default 1, created_at text default current_timestamp);
create table if not exists services(id integer primary key, name text not null, category text, code text, icon_path text, image_path text, color text default '#21c98b', cost_price real default 0, selling_price real default 0, gst real default 0, discount real default 0, remarks text, active integer default 1, display_order integer default 0);
create table if not exists companies(id integer primary key, logo_path text, name text not null, branch text, address text, phone text, email text, website text, gstin text, pan text, bank_details text, upi_qr_path text, signature_path text, stamp_path text, footer text, terms text, letterhead_path text, invoice_prefix text default 'INV-', invoice_suffix text default '', active integer default 1);
create table if not exists bill_series(id integer primary key, company_id integer, prefix text, suffix text, next_number integer default 1, number_length integer default 6, reset_mode text default 'manual', history_json text default '[]');
create table if not exists templates(id integer primary key, name text unique, category text, paper text, orientation text, background_path text, layout_json text not null, builtin integer default 0, active integer default 1);
create table if not exists invoices(id integer primary key, invoice_number text unique, customer_id integer, company_id integer, template_id integer, operator text, invoice_dt text, payment_mode text, subtotal real, gst_total real, discount_total real, grand_total real, status text, pdf_path text, png_path text, jpeg_path text, drive_link text, qr_path text, barcode_path text, remarks text, version_history text default '[]');
create table if not exists invoice_items(id integer primary key, invoice_id integer references invoices(id) on delete cascade, service_id integer, description text, quantity real, rate real, gst real, discount real, line_total real);
create table if not exists upload_queue(id integer primary key, invoice_id integer, local_path text, mime_type text, drive_folder text, status text default 'pending', attempts integer default 0, last_error text, created_at text default current_timestamp);
create table if not exists settings(key text primary key, value text); create table if not exists audit_logs(id integer primary key, ts text, username text, action text, entity text, entity_id text, details text);
'''
DEFAULT_LAYOUT={"invoice_number":[420,80,130,20],"invoice_date":[420,105,130,20],"customer_name":[50,155,250,22],"customer_mobile":[50,180,180,20],"items_table":[45,250,505,250],"grand_total":[390,535,160,25],"qr_code":[50,690,80,80],"footer":[160,760,280,25]}

@dataclass
class InvoiceItem: service_id:int; description:str; quantity:float; rate:float; gst:float; discount:float

class InvoiceEngine:
    def __init__(self,store:Store): self.store=store
    def next_number(self,company:sqlite3.Row)->str:
        row=self.store.one("select * from bill_series where company_id=?",(company["id"],))
        if not row:
            self.store.run("insert into bill_series(company_id,prefix,suffix,next_number,number_length) values(?,?,?,?,?)",(company["id"],company["invoice_prefix"],company["invoice_suffix"],1,6)); row=self.store.one("select * from bill_series where company_id=?",(company["id"],))
        number=f"{row['prefix']}{row['next_number']:0{row['number_length']}d}{row['suffix']}"; self.store.run("update bill_series set next_number=next_number+1 where id=?",(row["id"],)); return number
    def create_invoice(self,customer_id:int,items:list[InvoiceItem],payment_mode:str,operator:str,remarks:str="")->int:
        company=self.store.one("select * from companies where active=1 order by id limit 1"); template=self.store.one("select * from templates where active=1 order by builtin desc,id limit 1")
        inv_no=self.next_number(company); subtotal=gst_total=disc_total=grand=0.0
        for it in items:
            base=it.quantity*it.rate; disc=base*it.discount/100; gst=(base-disc)*it.gst/100; subtotal+=base; disc_total+=disc; gst_total+=gst; grand+=base-disc+gst
        inv_id=self.store.run("insert into invoices(invoice_number,customer_id,company_id,template_id,operator,invoice_dt,payment_mode,subtotal,gst_total,discount_total,grand_total,status,remarks) values(?,?,?,?,?,?,?,?,?,?,?,?,?)",(inv_no,customer_id,company['id'],template['id'],operator,now(),payment_mode,subtotal,gst_total,disc_total,grand,"Paid" if payment_mode else "Pending",remarks))
        for it in items: self.store.run("insert into invoice_items(invoice_id,service_id,description,quantity,rate,gst,discount,line_total) values(?,?,?,?,?,?,?,?)",(inv_id,it.service_id,it.description,it.quantity,it.rate,it.gst,it.discount,it.quantity*it.rate*(1-it.discount/100)*(1+it.gst/100)))
        paths=self.render(inv_id); self.store.run("update invoices set pdf_path=?, png_path=?, jpeg_path=?, qr_path=?, barcode_path=? where id=?",(*paths,inv_id));
        for p,m in [(paths[0],"application/pdf"),(paths[1],"image/png"),(paths[2],"image/jpeg")]: self.store.run("insert into upload_queue(invoice_id,local_path,mime_type,drive_folder) values(?,?,?,?)",(inv_id,p,m,self.folder(company['name'])))
        self.store.audit(operator,"create","invoice",str(inv_id),{"invoice_number":inv_no,"total":grand}); return inv_id
    def folder(self,company:str)->str:
        d=dt.date.today(); return f"Bills/{company}/{d:%Y}/{d:%B}/{d:%d-%m-%Y}"
    def render(self,inv_id:int, dpi:int=300)->tuple[str,str,str,str,str]:
        from reportlab.lib.pagesizes import A4; from reportlab.pdfgen import canvas; from reportlab.lib import colors
        from PIL import Image; import qrcode
        try:
            from barcode import Code128; from barcode.writer import ImageWriter
        except Exception: Code128=None
        inv=self.store.one("select * from invoices where id=?",(inv_id,)); cust=self.store.one("select * from customers where id=?",(inv['customer_id'],)); comp=self.store.one("select * from companies where id=?",(inv['company_id'],)); items=self.store.q("select * from invoice_items where invoice_id=?",(inv_id,))
        root=OUT/self.folder(comp['name']); (root/"PDF").mkdir(parents=True,exist_ok=True); (root/"PNG").mkdir(exist_ok=True); (root/"JPEG").mkdir(exist_ok=True)
        qr=str(root/f"{inv['invoice_number']}_qr.png"); qrcode.make(f"Invoice:{inv['invoice_number']}|Total:{inv['grand_total']}").save(qr)
        bar=str(root/f"{inv['invoice_number']}_barcode.png");
        if Code128: Code128(inv['invoice_number'],writer=ImageWriter()).save(bar[:-4])
        pdf=str(root/"PDF"/f"{inv['invoice_number']}.pdf"); c=canvas.Canvas(pdf,pagesize=A4); w,h=A4
        c.setFillColor(colors.HexColor('#0a2342')); c.rect(0,h-95,w,95,fill=1,stroke=0); c.setFillColor(colors.white); c.setFont('Helvetica-Bold',22); c.drawString(40,h-45,comp['name']); c.setFont('Helvetica',10); c.drawString(40,h-65,comp['address'] or ''); c.drawRightString(w-40,h-45,inv['invoice_number']); c.drawRightString(w-40,h-65,inv['invoice_dt'])
        c.setFillColor(colors.black); c.setFont('Helvetica-Bold',12); c.drawString(40,h-125,'Bill To'); c.setFont('Helvetica',10); c.drawString(40,h-145,cust['name']); c.drawString(40,h-160,cust['mobile'] or ''); c.drawString(40,h-175,cust['address'] or '')
        y=h-230; c.setFillColor(colors.HexColor('#21c98b')); c.rect(40,y,w-80,22,fill=1); c.setFillColor(colors.white); c.drawString(50,y+7,'Description'); c.drawRightString(360,y+7,'Qty'); c.drawRightString(430,y+7,'Rate'); c.drawRightString(500,y+7,'GST'); y-=24; c.setFillColor(colors.black)
        for it in items: c.drawString(50,y,it['description']); c.drawRightString(360,y,str(it['quantity'])); c.drawRightString(430,y,money(it['rate'])); c.drawRightString(500,y,money(it['line_total'])); y-=20
        c.setFont('Helvetica-Bold',13); c.drawRightString(w-40,120,f"Grand Total: {money(inv['grand_total'])}"); c.drawImage(qr,40,70,70,70,mask='auto'); c.setFont('Helvetica',9); c.drawCentredString(w/2,35,comp['footer'] or ''); c.save()
        import fitz; doc=fitz.open(pdf); page=doc[0]; pix=page.get_pixmap(matrix=fitz.Matrix(dpi/72,dpi/72),alpha=False); png=str(root/"PNG"/f"{inv['invoice_number']}.png"); jpg=str(root/"JPEG"/f"{inv['invoice_number']}.jpg"); pix.save(png); Image.open(png).save(jpg,quality=95,dpi=(dpi,dpi)); return pdf,png,jpg,qr,bar

# UI imports after dependency check message support
missing=missing_packages()
if missing and __name__=='__main__': print('Missing optional/required packages. Install with: pip install '+ ' '.join(missing))
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QBrush
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QPushButton,QLineEdit,QComboBox,QTableWidget,QTableWidgetItem,QGraphicsView,QGraphicsScene,QGraphicsRectItem,QDialog,QFormLayout,QDoubleSpinBox,QSpinBox,QMessageBox,QFileDialog,QFrame

class TemplateDesigner(QDialog):
    def __init__(self,store:Store):
        super().__init__(); self.store=store; self.setWindowTitle('Visual Template Designer'); self.resize(900,650)
        lay=QHBoxLayout(self); self.scene=QGraphicsScene(0,0,595,842); self.view=QGraphicsView(self.scene); lay.addWidget(self.view,1)
        side=QVBoxLayout(); lay.addLayout(side); row=store.one("select * from templates order by id limit 1"); layout=json.loads(row['layout_json'])
        for name,(x,y,w,h) in layout.items():
            item=QGraphicsRectItem(x,y,w,h); item.setFlag(item.GraphicsItemFlag.ItemIsMovable); item.setFlag(item.GraphicsItemFlag.ItemIsSelectable); item.setBrush(QBrush(QColor(33,201,139,70))); item.setToolTip(name); self.scene.addItem(item); txt=self.scene.addText(name); txt.setPos(x+3,y+3); txt.setDefaultTextColor(QColor('#0a2342'))
        save=QPushButton('Save Layout'); save.clicked.connect(lambda:self.save(row['id'])); side.addWidget(save); side.addStretch()
    def save(self,tid:int):
        layout={}
        for item in self.scene.items():
            if isinstance(item,QGraphicsRectItem): layout[item.toolTip()]=[round(item.pos().x()+item.rect().x(),1),round(item.pos().y()+item.rect().y(),1),round(item.rect().width(),1),round(item.rect().height(),1)]
        self.store.run('update templates set layout_json=? where id=?',(json.dumps(layout),tid)); QMessageBox.information(self,'Saved','Template layout saved permanently.')

class MainWindow(QMainWindow):
    def __init__(self): super().__init__(); self.store=Store(); self.engine=InvoiceEngine(self.store); self.user='admin'; self.setWindowTitle(APP_NAME); self.resize(1180,760); self.setWindowFlags(Qt.WindowType.FramelessWindowHint); self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.build()
    def build(self):
        root=QFrame(); root.setObjectName('root'); self.setCentralWidget(root); main=QHBoxLayout(root); nav=QVBoxLayout(); main.addLayout(nav); content=QVBoxLayout(); main.addLayout(content,1)
        for text,fn in [('Dashboard',self.dashboard),('Customers',self.customers),('Services',self.services),('Designer',lambda:TemplateDesigner(self.store).exec()),('New Bill',self.bill)]: b=QPushButton(text); b.clicked.connect(fn); nav.addWidget(b)
        close=QPushButton('×'); close.clicked.connect(self.close); nav.addStretch(); nav.addWidget(close); self.area=QVBoxLayout(); content.addLayout(self.area); self.dashboard(); self.setStyleSheet(STYLE)
    def clear(self):
        while self.area.count():
            i=self.area.takeAt(0); w=i.widget(); w and w.deleteLater()
    def dashboard(self):
        self.clear(); grid=QGridLayout(); self.area.addLayout(grid); stats=[('Today Sales',"select coalesce(sum(grand_total),0) v from invoices where date(invoice_dt)=date('now')"),('Customers','select count(*) v from customers'),('Services','select count(*) v from services where active=1'),('Pending Bills',"select count(*) v from invoices where status='Pending'")]
        for n,(label,sql) in enumerate(stats): val=self.store.one(sql)['v']; card=QLabel(f'<h3>{label}</h3><h1>{money(val) if "Sales" in label else val}</h1>'); card.setObjectName('card'); grid.addWidget(card,n//2,n%2)
    def customers(self): self.table_page('Customers','select id,name,mobile,email,outstanding_balance,active from customers', ['ID','Name','Mobile','Email','Outstanding','Active'])
    def services(self): self.table_page('Services','select id,name,category,selling_price,gst,active from services', ['ID','Name','Category','Price','GST','Active'])
    def table_page(self,title,sql,heads): self.clear(); self.area.addWidget(QLabel(f'<h1>{title}</h1>')); t=QTableWidget(); rows=self.store.q(sql); t.setColumnCount(len(heads)); t.setHorizontalHeaderLabels(heads); t.setRowCount(len(rows)); [t.setItem(r,c,QTableWidgetItem(str(row[c]))) for r,row in enumerate(rows) for c in range(len(heads))]; self.area.addWidget(t)
    def bill(self):
        self.clear(); form=QFormLayout(); self.area.addLayout(form); name=QLineEdit('Walk-in Customer'); mobile=QLineEdit(); svc=QComboBox(); services=self.store.q('select * from services where active=1'); [svc.addItem(f"{s['name']} - {money(s['selling_price'])}",s['id']) for s in services]; qty=QDoubleSpinBox(); qty.setValue(1); pay=QComboBox(); pay.addItems(['Cash','UPI','Card','Cheque','Bank Transfer','Wallet']); form.addRow('Customer',name); form.addRow('Mobile',mobile); form.addRow('Service',svc); form.addRow('Quantity',qty); form.addRow('Payment',pay); gen=QPushButton('Generate PDF / PNG / JPEG Invoice'); self.area.addWidget(gen)
        def do():
            cid=self.store.run('insert into customers(customer_id,name,mobile) values(?,?,?)',(str(uuid.uuid4())[:8],name.text(),mobile.text())); s=self.store.one('select * from services where id=?',(svc.currentData(),)); inv=self.engine.create_invoice(cid,[InvoiceItem(s['id'],s['name'],qty.value(),s['selling_price'],s['gst'],s['discount'])],pay.currentText(),self.user); row=self.store.one('select * from invoices where id=?',(inv,)); QMessageBox.information(self,'Invoice Generated',f"{row['invoice_number']}\nPDF: {row['pdf_path']}")
        gen.clicked.connect(do)
    def mousePressEvent(self,e): self._drag=e.globalPosition().toPoint()
    def mouseMoveEvent(self,e):
        if hasattr(self,'_drag'): self.move(self.pos()+e.globalPosition().toPoint()-self._drag); self._drag=e.globalPosition().toPoint()
STYLE='''#root{background:rgba(12,24,42,235);border-radius:18px;} QLabel{color:#eef7ff} QPushButton{background:#1667d8;color:white;border:0;border-radius:12px;padding:12px;font-weight:700} QPushButton:hover{background:#21c98b} QLineEdit,QComboBox,QDoubleSpinBox{padding:10px;border-radius:10px;background:#eef7ff} #card{background:rgba(255,255,255,35);border:1px solid rgba(255,255,255,50);border-radius:18px;padding:24px} QTableWidget{background:#eef7ff;border-radius:12px}'''

def main():
    app=QApplication(sys.argv); w=MainWindow(); w.show(); sys.exit(app.exec())
if __name__=='__main__': main()
