package co.visionairy.bluey;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RadialGradient;
import android.graphics.Shader;
import android.view.View;
import org.json.JSONObject;

final class FaceView extends View {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private static final int[] DIRECTIONS = {-1, 1};
    private Shader gradient;
    private float gazeX, gazeY, talk;
    private String mood = "listening";
    FaceView(Context context) { super(context); setContentDescription("Bluey. Double tap to wake or sleep. Press and hold to ask."); }
    void receive(JSONObject face) {
        gazeX = (float) Math.max(-1, Math.min(1, face.optDouble("gazeX", 0)));
        gazeY = (float) Math.max(-1, Math.min(1, face.optDouble("gazeY", 0)));
        talk = (float) Math.max(0, Math.min(1, face.optDouble("talk", 0)));
        mood = face.optString("mood", "listening");
        invalidate();
    }
    @Override protected void onSizeChanged(int width, int height, int oldWidth, int oldHeight) {
        super.onSizeChanged(width, height, oldWidth, oldHeight);
        float radius = Math.min(width * .32f, height * .40f);
        if (radius > 0) gradient = new RadialGradient(width/2f-radius*.35f, height/2f-radius*.45f, radius*1.8f,
            new int[]{Color.rgb(169,188,255),Color.rgb(108,134,245),Color.rgb(43,47,143)}, null, Shader.TileMode.CLAMP);
    }
    @Override public boolean performClick() { super.performClick(); return true; }
    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        canvas.drawColor(Color.BLACK);
        float cx = getWidth() / 2f, cy = getHeight() / 2f;
        float radius = Math.min(getWidth() * .32f, getHeight() * .40f);
        float bob = (float) Math.sin(System.currentTimeMillis() / 600.0) * radius * .015f;
        cy += bob - talk * radius * .04f;
        paint.setShader(gradient);
        canvas.drawCircle(cx, cy, radius, paint);
        paint.setShader(null);
        for (int direction : DIRECTIONS) {
            float ex = cx + direction * radius * .30f, ey = cy - radius * .12f;
            paint.setColor(Color.WHITE);
            canvas.drawOval(ex-radius*.22f,ey-radius*.28f,ex+radius*.22f,ey+radius*.28f,paint);
            paint.setColor(Color.rgb(28,31,102));
            if (mood.equals("sleepy")) {
                paint.setStrokeWidth(radius*.04f);
                canvas.drawLine(ex-radius*.15f,ey,ex+radius*.15f,ey,paint);
            } else {
                canvas.drawCircle(ex+gazeX*radius*.10f,ey+gazeY*radius*.12f,radius*.10f,paint);
            }
        }
        paint.setColor(Color.rgb(28,31,102));
        canvas.drawOval(cx-radius*.08f,cy+radius*.09f,cx+radius*.08f,cy+radius*.17f,paint);
        paint.setStyle(Paint.Style.STROKE); paint.setStrokeWidth(radius*.025f);
        canvas.drawArc(cx-radius*.14f,cy+radius*.20f,cx+radius*.14f,cy+radius*.37f,10,160,false,paint);
        paint.setStyle(Paint.Style.FILL);
        postInvalidateDelayed(33);
    }
}
