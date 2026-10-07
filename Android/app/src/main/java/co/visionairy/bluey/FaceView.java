package co.visionairy.bluey;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RadialGradient;
import android.graphics.Shader;
import android.os.SystemClock;
import android.view.View;
import org.json.JSONObject;

/** Android Canvas port of iOS FaceView's 844 x 390, bottom-cropped blueberry. */
final class FaceView extends View {
    private static final int NAVY = 0xff1c1f66, INK = 0xff17151f;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path blob = new Path(), detail = new Path(), eye = new Path();
    private final Spring gazeX = new Spring(0, 260, .82f), gazeY = new Spring(0, 260, .82f);
    private final Spring pupil = new Spring(1, 160, .5f), brow = new Spring(10, 180, .55f);
    private final Spring lean = new Spring(0, 60, .8f), hop = new Spring(0, 260, .35f);
    private final Shader skin = new LinearGradient(217, 90.9f, 627, 697.1f,
            new int[]{0xffa9bcff, 0xff6c86f5, 0xff4254d6, 0xff2b2f8f},
            new float[]{0, .34f, .68f, 1}, Shader.TileMode.CLAMP);
    private final Shader shine = new RadialGradient(258, 170, 243,
            new int[]{0x80ffffff, 0x00ffffff}, null, Shader.TileMode.CLAMP);
    private final Shader cheek = new RadialGradient(0, 0, 48,
            new int[]{0x70f3a6d8, 0x00f3a6d8}, null, Shader.TileMode.CLAMP);
    private final Shader glow = new RadialGradient(422, 330, 475,
            new int[]{0x604254d6, 0x004254d6}, new float[]{.65f, 1}, Shader.TileMode.CLAMP);
    private float targetX, targetY, targetTalk, talk;
    private String mood = "listening";
    private boolean speaking;
    void setSpeaking(boolean active) { speaking = active; invalidate(); }
    private long lastFrame, lastPacket, blinkStart, nextBlink, nextHop;

    private static final class Spring {
        float value, velocity;
        final float stiffness, damping;
        Spring(float value, float stiffness, float damping) {
            this.value = value; this.stiffness = stiffness; this.damping = damping;
        }
        void step(float target, float dt) {
            velocity += (stiffness * (target - value) - 2 * (float)Math.sqrt(stiffness) * damping * velocity) * dt;
            value += velocity * dt;
        }
    }

    FaceView(Context context) {
        super(context);
        setContentDescription("Bluey. Double tap to wake or sleep. Press and hold to ask.");
        // Same asymmetric cubic outline as iOS BlobShape (820 x 700 at 12,44).
        float x=12, y=44, w=820, h=700, k=.5523f;
        blob.moveTo(x+.52f*w,y);
        blob.cubicTo(x+w-.48f*w*(1-k),y,x+w,y+.56f*h*(1-k),x+w,y+.56f*h);
        blob.cubicTo(x+w,y+h-.44f*h*(1-k),x+w-.46f*w*(1-k),y+h,x+.54f*w,y+h);
        blob.cubicTo(x+.54f*w*(1-k),y+h,x,y+h-.42f*h*(1-k),x,y+.58f*h);
        blob.cubicTo(x,y+.58f*h*(1-k),x+.52f*w*(1-k),y,x+.52f*w,y);
        blob.close();
    }

    void receive(JSONObject face) {
        targetX = clamp((float)face.optDouble("gazeX",0), -1, 1);
        targetY = clamp((float)face.optDouble("gazeY",0), -1, 1);
        targetTalk = clamp((float)face.optDouble("talk",0), 0, 1);
        String next = face.optString("mood", "listening");
        long now = SystemClock.uptimeMillis();
        if (!next.equals(mood)) {
            blinkStart = now;
            if (!next.equals("sleepy") && !next.equals("resting")) hop.velocity += 160;
        }
        mood = next; lastPacket = now;
        invalidate();
    }
    private static float clamp(float v,float lo,float hi) { return Float.isFinite(v) ? Math.max(lo,Math.min(hi,v)) : 0; }
    private void fill(int color) { paint.setShader(null); paint.setStyle(Paint.Style.FILL); paint.setColor(color); }
    private void stroke(int color,float width) { fill(color); paint.setStyle(Paint.Style.STROKE); paint.setStrokeWidth(width); paint.setStrokeCap(Paint.Cap.ROUND); }
    @Override public boolean performClick() { super.performClick(); return true; }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        long now = SystemClock.uptimeMillis();
        float dt = lastFrame == 0 ? 1/60f : Math.min((now-lastFrame)/1000f, 1/30f);
        lastFrame = now;
        float time = now/1000f;
        boolean happy=mood.equals("happy"), sleepy=mood.equals("sleepy"), resting=mood.equals("resting"), thinking=mood.equals("thinking");
        boolean live = now-lastPacket < 2500;
        float wantX=live?targetX:(float)Math.sin(time*.7)*.45f;
        float wantY=live?targetY:-.25f+(float)Math.sin(time*.43)*.2f;
        if (thinking) { wantX=.6f; wantY=-.85f; }
        gazeX.step(wantX,dt); gazeY.step(wantY,dt);
        float speechTalk = speaking ? .5f+.35f*(float)(Math.sin(time*19)*Math.sin(time*7.3)) : 0;
        talk += (Math.max(speechTalk,live?targetTalk:0)-talk)*Math.min(1,dt*25);
        pupil.step(happy?1.2f:thinking?.9f:mood.equals("pointing")?.95f:1.12f,dt);
        brow.step(happy?16:sleepy?-10:resting?-8:mood.equals("pointing")?-4:10+talk*18,dt);
        lean.step(-gazeX.value*.045f,dt);
        if (now>nextHop) {
            if (nextHop!=0 && !sleepy && !resting && talk<.05f) hop.velocity+=180;
            nextHop=now+9000;
        }
        hop.step(0,dt);
        if (now>nextBlink) { if(nextBlink!=0) blinkStart=now; nextBlink=now+2600+(long)(Math.random()*2300); }
        float blinkPhase=(now-blinkStart)/(sleepy?700f:150f);
        float closed=blinkPhase>=0 && blinkPhase<=1?(float)Math.sin(Math.PI*blinkPhase):0;
        float bounce=-talk*16+(float)Math.sin(time*1.8)*3-hop.value;
        canvas.drawColor(Color.BLACK);
        canvas.save();
        float scale=Math.max(getWidth()/844f,getHeight()/390f);
        canvas.translate((getWidth()-844*scale)/2,getHeight()-390*scale);
        canvas.scale(scale,scale);
        canvas.translate(0,bounce);
        canvas.rotate((float)Math.toDegrees(lean.value),422,744);
        float stretch=1+clamp(hop.value/900,-.03f,.03f);
        canvas.scale(2-stretch,stretch,422,744);
        fill(Color.WHITE); paint.setShader(glow); canvas.drawRect(0,0,844,744,paint);
        paint.setShader(skin); canvas.drawPath(blob,paint);
        canvas.save(); canvas.clipPath(blob);
        paint.setShader(shine); canvas.drawPath(blob,paint);
        fill(0x59ffffff); canvas.drawOval(202,84,248,106,paint);
        canvas.restore();
        // Original ten-point blueberry crown, from the iPhone design.
        float[] crown={30,4,36,16,52,12,40,24,46,36,30,28,14,36,20,24,8,12,24,16};
        detail.reset();
        for(int i=0;i<crown.length;i+=2) {
            float x=380+crown[i]*1.4f,y=24-brow.value*.3f+crown[i+1]*1.4f;
            if(i==0)detail.moveTo(x,y);else detail.lineTo(x,y);
        }
        detail.close(); fill(NAVY); canvas.drawPath(detail,paint);
        for(int side=-1;side<=1;side+=2) {
            float ex=422+side*130,ey=201;
            canvas.save(); canvas.translate(ex+side*62,ey+117); canvas.scale(1,.48f);
            fill(Color.WHITE); paint.setShader(cheek); canvas.drawCircle(0,0,48,paint); canvas.restore();
            canvas.save(); canvas.translate(ex+side*6,ey-112-clamp(brow.value,-10,18)*.7f);
            canvas.rotate(thinking?side*-13:mood.equals("pointing")?side*8:0);
            detail.reset(); detail.moveTo(-38,6); detail.quadTo(0,-12,38,6);
            stroke(NAVY,14); canvas.drawPath(detail,paint); canvas.restore();
            if(resting || happy) {
                detail.reset(); detail.moveTo(ex-60,ey+(happy?34:6));
                detail.quadTo(ex,ey+(happy?-54:52),ex+60,ey+(happy?34:6));
                stroke(INK,happy?24:18); canvas.drawPath(detail,paint); continue;
            }
            float open=Math.max(.06f,1-closed)*(1-talk*.12f);
            eye.reset(); eye.addOval(ex-95,ey-95*open,ex+95,ey+95*open,Path.Direction.CW);
            fill(Color.WHITE); canvas.drawPath(eye,paint);
            if(open<=.2f)continue;
            float len=Math.max(1,(float)Math.hypot(gazeX.value,gazeY.value));
            float px=ex+gazeX.value/len*50-side*3,py=ey+gazeY.value/len*50*open;
            if(sleepy)py=Math.max(py,ey)+28;
            float r=46*pupil.value;
            canvas.save(); canvas.clipPath(eye);
            fill(INK); canvas.drawCircle(px,py,r,paint);
            fill(Color.WHITE); canvas.drawCircle(px-r*.30f,py-r*.44f,r*.28f,paint);
            fill(0xd9ffffff); canvas.drawCircle(px+r*.40f,py+r*.34f,r*.12f,paint);
            if(sleepy || mood.equals("pointing")) {
                fill(Color.WHITE); paint.setShader(skin);
                float bottom=sleepy?ey-95*open+190*open*(.5f+.06f*(float)Math.sin(time*1.3)):ey-95*open+20;
                canvas.drawRect(ex-100,ey-110,ex+100,bottom,paint);
            }
            canvas.restore();
        }
        float nw=60-talk*8,nh=38+talk*34,ny=316-talk*6;
        fill(NAVY);
        if(happy && talk<.1f) {
            detail.reset(); detail.moveTo(422-nw/2-8,ny+8); detail.quadTo(422,ny+58,422+nw/2+8,ny+8); detail.close(); canvas.drawPath(detail,paint);
        } else {
            canvas.drawOval(422-nw/2,ny,422+nw/2,ny+nh,paint);
            if(talk>.25f) { fill(0xe6e58bc4); canvas.drawOval(422-nw*.28f,ny+nh*.62f,422+nw*.28f,ny+nh*.92f,paint); }
        }
        if(thinking)for(int i=0;i<3;i++){ fill(Color.argb(255-i*76,255,255,255)); canvas.drawCircle(710+i*26,92-i*12+(float)Math.sin(time*3+i)*4,8,paint); }
        canvas.restore();
        postInvalidateOnAnimation();
    }
}
