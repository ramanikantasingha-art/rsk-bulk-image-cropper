"""Run with: python test_cropper.py. Uses an offscreen Qt window."""
import os, tempfile
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from bulk_image_cropper import *
from PyQt5.QtTest import QTest
app=QApplication([])
QMessageBox.information=lambda *a: QMessageBox.Ok
QMessageBox.warning=lambda *a: QMessageBox.Ok

def drag(w, start, end, shift=False):
    modifier=Qt.ShiftModifier if shift else Qt.NoModifier
    QTest.mousePress(w.view.viewport(),Qt.LeftButton,modifier,w.view.mapFromScene(start))
    QTest.mouseMove(w.view.viewport(),w.view.mapFromScene(end))
    QTest.mouseRelease(w.view.viewport(),Qt.LeftButton,modifier,w.view.mapFromScene(end))
    app.processEvents()

with tempfile.TemporaryDirectory() as d:
    inp=os.path.join(d,'in'); out=os.path.join(d,'out')
    os.mkdir(inp); os.mkdir(out)
    for n in [10,2,1]: Image.new('RGB',(800,600),(n,20,30)).save(os.path.join(inp,f'Page ({n}).png'))
    w=ImageCropperApp(); w.show(); app.processEvents()
    w.input_folder=inp; w.output_folder=out; w.load_images(); app.processEvents()
    assert w.image_files==['Page (1).png','Page (2).png','Page (10).png']
    base=QRectF(150,120,300,240)
    offsets={'nw':(-40,-30),'n':(0,-30),'ne':(40,-30),'e':(40,0),
             'se':(40,30),'s':(0,30),'sw':(-40,30),'w':(-40,0)}
    for locked in [False,True]:
        for name,(dx,dy) in offsets.items():
            w.chk_ratio.setChecked(False); w.update_crop_box(base)
            w.chk_ratio.setChecked(locked)
            point=w.view.handles()[name]
            assert w.view.hit_test(point)==name
            drag(w,point,point+QPointF(dx,dy))
            result=w.selection_rect
            assert result!=base, name
            assert w.view.image_bounds.contains(result), (name,result)
            if locked: assert abs(result.width()/result.height()-1.25)<0.02
    w.chk_ratio.setChecked(False); w.update_crop_box(base)
    drag(w,base.center(),base.center()+QPointF(60,40))
    assert abs(w.selection_rect.x()-210)<=2
    assert w.selection_rect.size()==base.size()
    drag(w,w.selection_rect.center(),QPointF(2000,2000))
    assert w.view.image_bounds.contains(w.selection_rect)
    assert w.selection_rect.size()==base.size()
    drag(w,QPointF(700,500),QPointF(100,80),True)
    assert abs(w.selection_rect.width()-600)<=2
    old=QRectF(w.selection_rect)
    for i in range(9):
        QTest.mouseClick(w.btn_next,Qt.LeftButton)
        assert w.selection_rect==old
        assert w.crop_rect.scene()==w.scene
    QTest.mouseClick(w.btn_prev,Qt.LeftButton); assert w.preview_index==2
    w.resize(950,720); app.processEvents(); assert w.selection_rect==old
    w.update_crop_box(QRectF(100,80,400,300))
    w.chk_apply_all.setChecked(False); w.process_bulk_crop(); w.worker.wait(); app.processEvents()
    assert len(os.listdir(out))==1
    w.chk_apply_all.setChecked(True); w.process_bulk_crop(); w.worker.wait(); app.processEvents()
    assert len(os.listdir(out))==3
    for f in os.listdir(out): assert Image.open(os.path.join(out,f)).size==(400,300)
    Image.new('RGB',(200,160)).save(os.path.join(inp,w.image_files[0]))
    w.preview_index=0; w.show_preview_image()
    assert w.selection_rect==QRectF(100,80,400,300)
    assert w.view.selection==QRectF(100,80,100,80)
    w.preview_index=2; w.show_preview_image()
    w.grab().save(os.path.join(tempfile.gettempdir(),'cropper_v2_test.png'))
    w.close()
print('PASS: 8 handles, locked/free resize, moving, boundaries, Shift-drag, numerical sort, navigation, resize, small previews and current/all exports.')
