#!/usr/bin/env python3
"""MSOS FORM GENERATOR PRO - single file PyQt6 desktop app."""
from __future__ import annotations

import io, json, os, re, sqlite3, sys, tempfile, uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from PyQt6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtGui import QAction, QIcon, QPainter, QPixmap, QColor, QFont
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QStackedWidget, QListWidget, QListWidgetItem, QComboBox, QLineEdit,
    QTextEdit, QFileDialog, QMessageBox, QFormLayout, QScrollArea, QSplitter,
    QSlider, QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QToolButton, QPlainTextEdit, QGroupBox, QGridLayout, QInputDialog
)

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from PIL import Image
import qrcode
try:
    import pytesseract
except Exception:
    pytesseract = None
try:
    from PyQt6.QtPdf import QPdfDocument
    from PyQt6.QtPdfWidgets import QPdfView
except Exception:
    QPdfDocument = None
    QPdfView = None

APP_NAME = "MSOS FORM GENERATOR PRO"
DB_PATH = Path.home() / ".msos_form_generator_pro.sqlite3"

BUILTIN_TEMPLATES = [
    {"id":"pan_update","title":{"en":"PAN Card Update Consent Form","te":"పాన్ కార్డ్ నవీకరణ సమ్మతి పత్రం","hi":"पैन कार्ड अपडेट सहमति फॉर्म"},"fields":["Name","Aadhaar","Mobile","Address","PAN Number","Correction Required"],"body":{"en":"I hereby authorize the service center to process my PAN card update request using the details provided below.","te":"క్రింద ఇచ్చిన వివరాలతో నా పాన్ కార్డ్ నవీకరణ అభ్యర్థనను ప్రాసెస్ చేయడానికి సేవా కేంద్రానికి నేను అనుమతిస్తున్నాను.","hi":"मैं नीचे दिए गए विवरणों के आधार पर अपने पैन कार्ड अपडेट अनुरोध को संसाधित करने के लिए सेवा केंद्र को अधिकृत करता/करती हूँ।"}},
    {"id":"aadhaar_update","title":{"en":"Aadhaar Update Consent Form","te":"ఆధార్ నవీకరణ సమ్మతి పత్రం","hi":"आधार अपडेट सहमति फॉर्म"},"fields":["Name","Aadhaar","Mobile","Address","Update Type","Date of Birth"],"body":{"en":"I consent to update my Aadhaar information as per the supporting documents submitted by me.","te":"నేను సమర్పించిన పత్రాల ప్రకారం నా ఆధార్ సమాచారాన్ని నవీకరించడానికి నేను అంగీకరిస్తున్నాను.","hi":"मैं अपने द्वारा जमा किए गए दस्तावेजों के अनुसार आधार जानकारी अपडेट करने की सहमति देता/देती हूँ।"}},
    {"id":"voter_update","title":{"en":"Voter ID Update Consent Form","te":"ఓటర్ ఐడి నవీకరణ సమ్మతి పత్రం","hi":"मतदाता पहचान पत्र अपडेट सहमति फॉर्म"},"fields":["Name","Aadhaar","Mobile","Address","Voter ID","Assembly Constituency"],"body":{"en":"I request correction or update of my Voter ID details and confirm that the information is true.","te":"నా ఓటర్ ఐడి వివరాలను సరిచేయమని లేదా నవీకరించమని కోరుతూ సమాచారం నిజమని ధృవీకరిస్తున్నాను.","hi":"मैं अपने मतदाता पहचान पत्र विवरण में सुधार या अपडेट का अनुरोध करता/करती हूँ और जानकारी सही होने की पुष्टि करता/करती हूँ।"}},
    {"id":"pan_recovery","title":{"en":"PAN Recovery Consent Form","te":"పాన్ రికవరీ సమ్మతి పత్రం","hi":"पैन रिकवरी सहमति फॉर्म"},"fields":["Name","Aadhaar","Mobile","Address","Father Name","Date of Birth"],"body":{"en":"I authorize retrieval of my PAN information for recovery support through the service center.","te":"సేవా కేంద్రం ద్వారా రికవరీ సహాయం కోసం నా పాన్ సమాచారాన్ని పొందడానికి నేను అనుమతిస్తున్నాను.","hi":"मैं सेवा केंद्र के माध्यम से रिकवरी सहायता के लिए अपनी पैन जानकारी प्राप्त करने की अनुमति देता/देती हूँ।"}},
    {"id":"general_decl","title":{"en":"General Declaration Form","te":"సాధారణ ప్రకటన పత్రం","hi":"सामान्य घोषणा फॉर्म"},"fields":["Name","Aadhaar","Mobile","Address","Purpose","Declaration"],"body":{"en":"I declare that all information furnished by me is correct to the best of my knowledge.","te":"నేను ఇచ్చిన సమాచారం నా జ్ఞానానికి సరైనదని ప్రకటిస్తున్నాను.","hi":"मैं घोषणा करता/करती हूँ कि मेरे द्वारा दी गई सभी जानकारी मेरी जानकारी के अनुसार सही है।"}},
]

LANGS = {"en":"English", "te":"Telugu", "hi":"Hindi"}

class Database:
    def __init__(self, path=DB_PATH):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript('''
        CREATE TABLE IF NOT EXISTS templates(id INTEGER PRIMARY KEY, name TEXT UNIQUE, data TEXT, builtin INTEGER DEFAULT 0, created_at TEXT);
        CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY, name TEXT, aadhaar TEXT, mobile TEXT, address TEXT, data TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS generated_forms(id INTEGER PRIMARY KEY, template_name TEXT, customer_name TEXT, file_path TEXT, data TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        ''')
        self.conn.commit(); self.seed()
    def seed(self):
        for t in BUILTIN_TEMPLATES:
            self.conn.execute("INSERT OR IGNORE INTO templates(name,data,builtin,created_at) VALUES(?,?,1,?)", (t['title']['en'], json.dumps(t,ensure_ascii=False), datetime.now().isoformat()))
        self.conn.commit()
    def templates(self): return [dict(r) for r in self.conn.execute("SELECT * FROM templates ORDER BY builtin DESC,name")]
    def upsert_template(self, name, data):
        self.conn.execute("INSERT INTO templates(name,data,builtin,created_at) VALUES(?,?,0,?) ON CONFLICT(name) DO UPDATE SET data=excluded.data", (name,json.dumps(data,ensure_ascii=False),datetime.now().isoformat())); self.conn.commit()
    def setting(self,k,d=""): return self.conn.execute("SELECT value FROM settings WHERE key=?",(k,)).fetchone()[0] if self.conn.execute("SELECT value FROM settings WHERE key=?",(k,)).fetchone() else d
    def set_setting(self,k,v): self.conn.execute("INSERT OR REPLACE INTO settings VALUES(?,?)",(k,v)); self.conn.commit()
    def add_customer(self, data):
        self.conn.execute("INSERT INTO customers(name,aadhaar,mobile,address,data,created_at) VALUES(?,?,?,?,?,?)", (data.get('Name',''),data.get('Aadhaar',''),data.get('Mobile',''),data.get('Address',''),json.dumps(data,ensure_ascii=False),datetime.now().isoformat())); self.conn.commit()
    def customers(self, q=""):
        like=f"%{q}%"; return [dict(r) for r in self.conn.execute("SELECT * FROM customers WHERE name LIKE ? OR mobile LIKE ? OR aadhaar LIKE ? ORDER BY id DESC",(like,like,like))]
    def add_form(self, tpl, cust, path, data):
        self.conn.execute("INSERT INTO generated_forms(template_name,customer_name,file_path,data,created_at) VALUES(?,?,?,?,?)",(tpl,cust,path,json.dumps(data,ensure_ascii=False),datetime.now().isoformat())); self.conn.commit()

def tr(obj, lang):
    if isinstance(obj, dict): return obj.get(lang) or obj.get('en') or next(iter(obj.values()), '')
    return str(obj)

def wrap_text(c, text, x, y, width, style, leading=14):
    for para in str(text).split('\n'):
        words=para.split(); line=''
        for w in words:
            test=(line+' '+w).strip()
            if stringWidth(test, style.fontName, style.fontSize) <= width: line=test
            else: c.drawString(x,y,line); y-=leading; line=w
        if line: c.drawString(x,y,line); y-=leading
        y-=3
    return y

class PdfGenerator:
    @staticmethod
    def create(template, data, path, lang='en', logo='', opacity=18, position='Center'):
        c=canvas.Canvas(path, pagesize=A4); w,h=A4
        if logo and Path(logo).exists():
            c.saveState(); c.setFillAlpha(opacity/100)
            if position == 'Bottom Corner': iw=38*mm; x=w-iw-18*mm; y=18*mm
            else: iw=95*mm; x=(w-iw)/2; y=(h-iw)/2
            c.drawImage(logo,x,y,iw,iw,mask='auto',preserveAspectRatio=True,anchor='c'); c.restoreState()
        c.setStrokeColor(colors.HexColor('#0b7f5f')); c.setLineWidth(2); c.rect(12*mm,12*mm,w-24*mm,h-24*mm)
        c.setFillColor(colors.HexColor('#0d47a1')); c.setFont('Helvetica-Bold',18); c.drawCentredString(w/2,h-25*mm,tr(template['title'],lang))
        c.setFont('Helvetica',11); c.setFillColor(colors.black)
        y=h-42*mm; y=wrap_text(c, tr(template.get('body',''),lang), 22*mm,y,w-44*mm,c._fontname and type('S',(),{'fontName':'Helvetica','fontSize':11})())
        c.setFont('Helvetica-Bold',13); c.setFillColor(colors.HexColor('#0b7f5f')); c.drawString(22*mm,y-4*mm,'Customer Details'); y-=13*mm
        c.setFont('Helvetica',11); c.setFillColor(colors.black)
        for f in template.get('fields',[]):
            val=str(data.get(f,'')); c.setFont('Helvetica-Bold',10.5); c.drawString(24*mm,y,f+':'); c.setFont('Helvetica',10.5)
            y=wrap_text(c,val,62*mm,y,w-84*mm,type('S',(),{'fontName':'Helvetica','fontSize':10.5})(),13)
            y-=2*mm
            if y<55*mm: c.showPage(); y=h-25*mm
        qrdata=json.dumps({'id':str(uuid.uuid4())[:8],'template':tr(template['title'],lang),'name':data.get('Name',''),'date':datetime.now().isoformat()},ensure_ascii=False)
        img=qrcode.make(qrdata); bio=io.BytesIO(); img.save(bio,format='PNG'); bio.seek(0)
        c.drawInlineImage(Image.open(bio), 22*mm, 28*mm, 28*mm, 28*mm)
        c.line(w-75*mm,43*mm,w-22*mm,43*mm); c.drawString(w-70*mm,36*mm,'Applicant Signature')
        c.setFont('Helvetica',8); c.setFillColor(colors.grey); c.drawCentredString(w/2,17*mm,f'Generated by {APP_NAME} on {datetime.now():%d-%m-%Y %H:%M}')
        c.save(); return path

class TitleBar(QFrame):
    def __init__(self, parent):
        super().__init__(); self.parent=parent; self.start=None; self.setObjectName('titleBar')
        lay=QHBoxLayout(self); lay.setContentsMargins(12,0,6,0); lay.addWidget(QLabel('🧾  '+APP_NAME)); lay.addStretch()
        for txt,fn in [('—',parent.showMinimized),('□',parent.toggle_max),('✕',parent.close)]:
            b=QPushButton(txt); b.setFixedSize(36,30); b.clicked.connect(fn); lay.addWidget(b)
    def mousePressEvent(self,e): self.start=e.globalPosition().toPoint()-self.parent.frameGeometry().topLeft()
    def mouseMoveEvent(self,e):
        if self.start and not self.parent.isMaximized(): self.parent.move(e.globalPosition().toPoint()-self.start)

class PreviewDialog(QDialog):
    def __init__(self, pdf):
        super().__init__(); self.setWindowTitle('A4 Preview'); self.resize(850,900); v=QVBoxLayout(self); tools=QHBoxLayout(); v.addLayout(tools)
        self.zoom=100; tools.addWidget(QLabel('Zoom')); s=QSlider(Qt.Orientation.Horizontal); s.setRange(50,200); s.setValue(100); tools.addWidget(s)
        if QPdfDocument:
            doc=QPdfDocument(self); doc.load(pdf); view=QPdfView(); view.setDocument(doc); view.setZoomMode(QPdfView.ZoomMode.Custom); v.addWidget(view); s.valueChanged.connect(lambda z:(view.setZoomFactor(z/100)))
        else:
            v.addWidget(QLabel('PDF preview requires PyQt6 QtPdfWidgets. File created:\n'+pdf))
        p=QPushButton('Print'); p.clicked.connect(lambda: self.print_pdf(pdf)); tools.addWidget(p)
    def print_pdf(self,pdf):
        printer=QPrinter(QPrinter.PrinterMode.HighResolution); dlg=QPrintDialog(printer,self); dlg.exec()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.db=Database(); self.inputs={}; self.current_template=None
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint); self.resize(1280,820)
        root=QWidget(); self.setCentralWidget(root); v=QVBoxLayout(root); v.setContentsMargins(0,0,0,0); v.addWidget(TitleBar(self))
        main=QHBoxLayout(); v.addLayout(main); self.nav=QListWidget(); self.nav.setFixedWidth(230); main.addWidget(self.nav)
        for icon,name in [('🏠','Dashboard'),('📝','Create Form'),('📥','Upload Form'),('📚','Templates Manager'),('👥','Customer Records'),('⚙️','Settings')]: self.nav.addItem(QListWidgetItem(f'{icon}  {name}'))
        self.stack=QStackedWidget(); main.addWidget(self.stack); self.pages=[self.dashboard(),self.create_page(),self.upload_page(),self.templates_page(),self.customers_page(),self.settings()]
        for p in self.pages: self.stack.addWidget(p)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex); self.nav.setCurrentRow(0); self.style()
    def toggle_max(self): self.showNormal() if self.isMaximized() else self.showMaximized()
    def style(self): self.setStyleSheet('''QMainWindow{background:#eef7fb} #titleBar{background:#063b73;color:white;min-height:42px} QLabel{font-size:14px} QPushButton{background:#0b8f65;color:white;border:0;border-radius:8px;padding:9px 14px} QPushButton:hover{background:#10a878} QListWidget{background:#073763;color:white;border:0;font-size:16px;padding:12px} QListWidget::item{padding:14px;border-radius:10px} QListWidget::item:selected{background:#0b8f65} QLineEdit,QTextEdit,QPlainTextEdit,QComboBox{background:white;border:1px solid #c9dfea;border-radius:8px;padding:8px} QGroupBox{font-weight:bold;border:1px solid #bdd8e8;border-radius:12px;margin-top:12px;padding:12px;background:#fafdff}''')
    def card(self,title): w=QWidget(); l=QVBoxLayout(w); h=QLabel(title); h.setFont(QFont('Arial',22,QFont.Weight.Bold)); l.addWidget(h); return w,l
    def dashboard(self):
        w,l=self.card('Dashboard'); l.addWidget(QLabel('Professional CSC / PAN / Aadhaar / Voter ID form generation suite.'))
        g=QGridLayout(); l.addLayout(g)
        for i,(t,n) in enumerate([('Built-in Templates',len(BUILTIN_TEMPLATES)),('Customers',len(self.db.customers())),('Database',str(DB_PATH)),('Print Ready','A4 PDF + QR')]):
            box=QGroupBox(t); bl=QVBoxLayout(box); lab=QLabel(str(n)); lab.setFont(QFont('Arial',20,QFont.Weight.Bold)); bl.addWidget(lab); g.addWidget(box,i//2,i%2)
        l.addStretch(); return w
    def create_page(self):
        w,l=self.card('Create Form'); top=QHBoxLayout(); l.addLayout(top); self.tpl_combo=QComboBox(); self.lang=QComboBox(); self.lang.addItems(LANGS.values()); top.addWidget(QLabel('Template')); top.addWidget(self.tpl_combo); top.addWidget(QLabel('Language')); top.addWidget(self.lang)
        sp=QSplitter(); l.addWidget(sp); formw=QScrollArea(); formw.setWidgetResizable(True); inner=QWidget(); self.form=QFormLayout(inner); formw.setWidget(inner); sp.addWidget(formw)
        right=QVBoxLayout(); rw=QWidget(); rw.setLayout(right); self.preview=QTextEdit(); self.preview.setReadOnly(True); right.addWidget(QLabel('Live Preview')); right.addWidget(self.preview)
        for text,fn in [('Save Customer',self.save_customer),('Preview Window',self.preview_pdf),('Export PDF',self.export_pdf),('Print',self.print_form)]: b=QPushButton(text); b.clicked.connect(fn); right.addWidget(b)
        sp.addWidget(rw); self.reload_templates(); self.tpl_combo.currentIndexChanged.connect(self.build_fields); self.lang.currentIndexChanged.connect(self.update_preview); return w
    def reload_templates(self): self.tpl_combo.clear(); [self.tpl_combo.addItem(r['name'],r['data']) for r in self.db.templates()]; self.build_fields()
    def selected_lang(self): return list(LANGS)[self.lang.currentIndex()]
    def build_fields(self):
        while self.form.rowCount(): self.form.removeRow(0)
        self.inputs={}; raw=self.tpl_combo.currentData(); self.current_template=json.loads(raw) if raw else BUILTIN_TEMPLATES[0]
        for f in self.current_template.get('fields',[]): inp=QLineEdit(); inp.textChanged.connect(self.update_preview); self.inputs[f]=inp; self.form.addRow(f,inp)
        self.update_preview()
    def data(self): return {k:v.text() for k,v in self.inputs.items()}
    def update_preview(self):
        if not self.current_template: return
        lines=[tr(self.current_template['title'],self.selected_lang()),'',tr(self.current_template.get('body',''),self.selected_lang()),'']+[f'{k}: {v}' for k,v in self.data().items()]
        self.preview.setPlainText('\n'.join(lines))
    def settings(self):
        w,l=self.card('Settings'); self.logo=QLineEdit(self.db.setting('logo')); self.savepath=QLineEdit(self.db.setting('savepath',str(Path.home()/ 'Documents'))); self.opacity=QSlider(Qt.Orientation.Horizontal); self.opacity.setRange(1,60); self.opacity.setValue(int(self.db.setting('opacity','18'))); self.pos=QComboBox(); self.pos.addItems(['Center','Bottom Corner'])
        for label,widget in [('Watermark logo PNG',self.logo),('Default save path',self.savepath),('Watermark position',self.pos)]: row=QHBoxLayout(); row.addWidget(QLabel(label)); row.addWidget(widget); l.addLayout(row)
        browse=QPushButton('Browse Logo'); browse.clicked.connect(lambda:self.logo.setText(QFileDialog.getOpenFileName(self,'Logo','','Images (*.png *.jpg *.jpeg)')[0] or self.logo.text())); l.addWidget(browse); l.addWidget(QLabel('Opacity')); l.addWidget(self.opacity)
        b=QPushButton('Save Settings'); b.clicked.connect(self.save_settings); l.addWidget(b); l.addStretch(); return w
    def save_settings(self):
        for k,w in [('logo',self.logo),('savepath',self.savepath)]: self.db.set_setting(k,w.text())
        self.db.set_setting('opacity',str(self.opacity.value())); self.db.set_setting('position',self.pos.currentText()); QMessageBox.information(self,'Saved','Settings saved')
    def pdf_path(self, ask=True):
        base=Path(self.db.setting('savepath',str(Path.home()))); base.mkdir(parents=True,exist_ok=True); default=str(base/(f"form_{datetime.now():%Y%m%d_%H%M%S}.pdf"))
        return QFileDialog.getSaveFileName(self,'Save PDF',default,'PDF (*.pdf)')[0] if ask else default
    def make_pdf(self,path):
        PdfGenerator.create(self.current_template,self.data(),path,self.selected_lang(),self.db.setting('logo'),int(self.db.setting('opacity','18')),self.db.setting('position','Center'))
        self.db.add_form(tr(self.current_template['title'],'en'), self.data().get('Name',''), path, self.data()); return path
    def export_pdf(self):
        p=self.pdf_path(True); 
        if p: self.make_pdf(p); QMessageBox.information(self,'Exported',p)
    def preview_pdf(self): p=self.make_pdf(str(Path(tempfile.gettempdir())/'msos_preview.pdf')); PreviewDialog(p).exec()
    def print_form(self): self.preview_pdf()
    def save_customer(self): self.db.add_customer(self.data()); QMessageBox.information(self,'Saved','Customer record saved')
    def upload_page(self):
        w,l=self.card('Upload Form'); self.ocr=QPlainTextEdit(); l.addWidget(QLabel('Upload PDF/Image, OCR text, edit labels one per line, then save as template.')); b=QPushButton('Upload and OCR'); b.clicked.connect(self.do_ocr); l.addWidget(b); l.addWidget(self.ocr); s=QPushButton('Save As Template'); s.clicked.connect(self.save_ocr_template); l.addWidget(s); return w
    def do_ocr(self):
        f=QFileDialog.getOpenFileName(self,'Open','','PDF/Images (*.pdf *.png *.jpg *.jpeg *.bmp)')[0]
        if not f: return
        text=''
        if pytesseract and not f.lower().endswith('.pdf'):
            text=pytesseract.image_to_string(Image.open(f))
        else: text='OCR for PDFs requires system converters; manually edit detected fields below.\nName\nAadhaar\nMobile\nAddress'
        labels=re.findall(r'([A-Za-z][A-Za-z /]{2,25})[:\n]', text) or ['Name','Aadhaar','Mobile','Address']
        self.ocr.setPlainText('\n'.join(dict.fromkeys([x.strip() for x in labels])))
    def save_ocr_template(self):
        name,ok=QInputDialog.getText(self,'Template Name','Name:')
        if ok and name:
            fields=[x.strip() for x in self.ocr.toPlainText().splitlines() if x.strip()]
            self.db.upsert_template(name,{'id':str(uuid.uuid4()),'title':{'en':name},'fields':fields,'body':{'en':'Custom uploaded form declaration.'}}); self.reload_templates(); QMessageBox.information(self,'Saved','Template saved')
    def templates_page(self):
        w,l=self.card('Templates Manager'); self.tpl_editor=QPlainTextEdit(); l.addWidget(QLabel('Edit template JSON and save.')); l.addWidget(self.tpl_editor); b=QPushButton('Load Selected Template'); b.clicked.connect(lambda:self.tpl_editor.setPlainText(json.dumps(self.current_template,indent=2,ensure_ascii=False))); l.addWidget(b); s=QPushButton('Save JSON Template'); s.clicked.connect(self.save_json_template); l.addWidget(s); return w
    def save_json_template(self):
        data=json.loads(self.tpl_editor.toPlainText()); self.db.upsert_template(tr(data['title'],'en'),data); self.reload_templates(); QMessageBox.information(self,'Saved','Template updated')
    def customers_page(self):
        w,l=self.card('Customer Records'); q=QLineEdit(); q.setPlaceholderText('Search by name/mobile/aadhaar'); l.addWidget(q); table=QTableWidget(0,4); table.setHorizontalHeaderLabels(['Name','Aadhaar','Mobile','Address']); table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); l.addWidget(table)
        def fill():
            rows=self.db.customers(q.text()); table.setRowCount(len(rows))
            for r,row in enumerate(rows):
                for c,k in enumerate(['name','aadhaar','mobile','address']): table.setItem(r,c,QTableWidgetItem(str(row[k])))
        q.textChanged.connect(fill); fill(); return w

if __name__ == '__main__':
    app=QApplication(sys.argv); app.setApplicationName(APP_NAME); win=MainWindow(); win.show(); sys.exit(app.exec())
