from flask import Flask, render_template, request, send_from_directory, redirect, url_for
import os
import subprocess

app = Flask(__name__)

# --เพิ่มเข้ามา-- กำหนดขนาดไฟล์สูงสุดที่อัปโหลดได้ (300 MB)
app.config['MAX_CONTENT_LENGTH'] = 300 * 1024 * 1024 

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --เพิ่มเข้ามา-- ฟังก์ชันสำหรับเช็คว่าเป็นไฟล์ .mp4 หรือไม่
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'mp4'}


def get_video_duration(input_filepath):
    ffprobe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", input_filepath]
    try:
        result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"Error getting duration: {e}")
        return None

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        video_file = request.files.get('video')
        if not video_file or not video_file.filename:
            return "กรุณาเลือกไฟล์วิดีโอ"

        # --เพิ่มเข้ามา-- ตรวจสอบประเภทไฟล์
        if not allowed_file(video_file.filename):
            return "อัปโหลดได้เฉพาะไฟล์ .mp4 เท่านั้น"

        input_filename = video_file.filename
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
        video_file.save(input_path)

        duration = get_video_duration(input_path)
        if not duration:
            os.remove(input_path)
            return "ไม่สามารถหาความยาวของวิดีโอได้"

        target_filesize_mb = 9.0
        audio_bitrate_kbps = 128
        target_total_bitrate_kbps = (target_filesize_mb * 8 * 1024) / duration
        video_bitrate_kbps = target_total_bitrate_kbps - audio_bitrate_kbps

        if video_bitrate_kbps <= 0:
            os.remove(input_path)
            return "วิดีโอนี้สั้นเกินไป ไม่สามารถบีบอัดให้ได้ขนาดตามเป้าหมาย"

        output_filename = f"compressed_{input_filename}"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        
        ffmpeg_command = ["ffmpeg", "-y", "-i", input_path, "-c:v", "libx264", "-b:v", f"{video_bitrate_kbps:.0f}k", "-c:a", "aac", "-b:a", f"{audio_bitrate_kbps}k", output_path]

        try:
            subprocess.run(ffmpeg_command, check=True)
            os.remove(input_path) # ลบไฟล์ต้นฉบับ
            return redirect(url_for('success_page', filename=output_filename))
        except Exception as e:
            return f"เกิดข้อผิดพลาดระหว่างการบีบอัด: {e}"

    return render_template('index.html')

@app.route('/success/<filename>')
def success_page(filename):
    return render_template('download.html', filename=filename)

# --- เพิ่ม Route ใหม่สำหรับลบไฟล์ ---
@app.route('/cleanup', methods=['POST'])
def cleanup():
    """
    ลบไฟล์ทั้งหมดในโฟลเดอร์ uploads แล้วกลับไปหน้าแรก
    """
    folder = app.config['UPLOAD_FOLDER']
    # วนลูปไฟล์ทั้งหมดในโฟลเดอร์
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path) # ลบไฟล์
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')
    
    # กลับไปที่หน้าแรก
    return redirect(url_for('home'))


@app.route('/uploads/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)

