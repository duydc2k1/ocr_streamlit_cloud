import streamlit as st
import requests
import base64
from PIL import Image
from io import BytesIO
import fitz  # PyMuPDF


st.set_page_config(page_title="SMART DIGIWORLD AI", layout="wide")
st.title("Chatbot OCR với SMART DIGIWORLD AI")


if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
     # **FIX: Thêm lời chào vào lần đầu tiên khởi tạo session state**
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": "Chào mừng bạn đến với Chatbot AI OCR sản phẩm của SMART DIGIWORLD. Vui lòng tải lên một file ảnh hoặc PDF ở thanh bên trái để bắt đầu."
    })


def image_to_base64(img: Image.Image) -> str:
    """Chuyển đổi một đối tượng ảnh PIL thành chuỗi base64."""
    buffered = BytesIO()
    # Chuyển sang RGB để đảm bảo tính nhất quán
    img.convert("RGB").save(buffered, format="JPEG", quality=95)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def pdf_to_images_base64(pdf_file, max_pages=5, dpi=200):
    """Chuyển đổi các trang của một file PDF thành danh sách chuỗi base64."""
    images_base64 = []
    try:
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        for page_number in range(min(len(doc), max_pages)):
            page = doc.load_page(page_number)
            # DPI cao hơn cho chất lượng ảnh tốt hơn
            pix = page.get_pixmap(dpi=dpi)
            image = Image.open(BytesIO(pix.tobytes()))
            image_base64 = image_to_base64(image)
            images_base64.append(image_base64)
    except Exception as e:
        st.error(f"Lỗi khi xử lý PDF: {e}")
        return None
    return images_base64


with st.sidebar:
    st.header("📁 Tải lên tài liệu")
    uploaded_file = st.file_uploader(
        "Tải lên ảnh hoặc PDF file", 
        type=["png", "jpg", "jpeg", "pdf"]
    )
    if uploaded_file:
        st.success(f"Đã tải lên: {uploaded_file.name}")

user_input = st.chat_input("💬 Nhập các trường thông tin cần trích xuất")


if user_input is not None:
   # **FIX 1: Thêm System Prompt vào đầu mỗi yêu cầu**
    # Đây là chỉ dẫn cố định cho mô hình trong suốt cuộc hội thoại.
    system_prompt = {
        "role": "system",
        "content": "Bạn là một chuyên gia trích xuất thông tin. Nhiệm vụ của bạn trích xuất các trường thông tin từ hình ảnh được cung cấp, sau đó chỉ trả về các trường thông tin đó dưới định dạng JSON. Các trường không có thông tin trả về null"
    }

    # Bắt đầu xây dựng payload với system prompt
    messages_to_send = [system_prompt]
    
    # Thêm lịch sử hội thoại vào payload để mô hình có ngữ cảnh
    messages_to_send.extend(st.session_state.chat_history)
    
    # Chuẩn bị nội dung của người dùng (văn bản + ảnh)
    user_content = []
    user_display_message = user_input # Tin nhắn để hiển thị lại cho người dùng
    
    # Mặc định câu hỏi nếu người dùng không nhập gì
    prompt_text = user_input or "Hãy trích xuất thông tin từ tài liệu sau"
    user_content.append({"type": "text", "text": prompt_text})

    if uploaded_file:
        file_type = uploaded_file.type
        image_b64_list = []
        
        with st.spinner(f"Đang xử lý file {uploaded_file.name}..."):
            if "pdf" in file_type:
                image_b64_list = pdf_to_images_base64(uploaded_file)
                user_display_message += f"\n*(Đã đính kèm {len(image_b64_list)} trang từ file PDF: {uploaded_file.name})*"
            else:
                image = Image.open(uploaded_file)
                image_b64_list.append(image_to_base64(image))
                user_display_message += f"\n*(Đã đính kèm ảnh: {uploaded_file.name})*"
        
        if image_b64_list:
            for img_b64 in image_b64_list:
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                })

    # Thêm tin nhắn hoàn chỉnh của người dùng vào payload
    messages_to_send.append({"role": "user", "content": user_content})
    
    # **FIX 2: Cải thiện logic lưu lịch sử hội thoại**
    # Lưu tin nhắn hiển thị của người dùng vào session state
    st.session_state.chat_history.append({"role": "user", "content": user_display_message})

    # Chuẩn bị payload cuối cùng để gửi đi
    payload = {
    
        "model": "/home/user/LLaMA-Factory/output/qwen2_5vl_lora_sft", 
        "messages": messages_to_send,
        "temperature": 0.3, # Giảm nhiệt độ để kết quả nhất quán hơn
        "max_tokens": 2048
    }

    # Gửi yêu cầu tới API
    with st.spinner("⏳ AI đang phân tích..."):
        try:
            # Thay thế bằng địa chỉ IP và cổng của vLLM server
            api_url = "http://203.180.14.72:8000/v1/chat/completions"
            response = requests.post(api_url, json=payload, timeout=200)
            response.raise_for_status() # Kiểm tra lỗi HTTP
            
            reply = response.json()['choices'][0]['message']['content']
            
            # Lưu câu trả lời của AI vào session state
            st.session_state.chat_history.append({"role": "assistant", "content": reply})

        except requests.exceptions.RequestException as e:
            st.error(f"Lỗi kết nối đến API: {e}")
        except Exception as e:
            st.error(f"Đã xảy ra lỗi không mong muốn: {e}")
            st.error(f"Phản hồi từ server (nếu có): {response.text if 'response' in locals() else 'Không có'}")

# --- Hiển thị lịch sử hội thoại ---
# **FIX 4: Đơn giản hóa vòng lặp hiển thị**
for msg in st.session_state.chat_history:
    role = msg["role"]
    with st.chat_message(role):
        st.markdown(msg["content"])

# Xóa file đã tải lên sau khi xử lý để sẵn sàng cho lần tiếp theo
if 'uploaded_file' in locals() and uploaded_file is not None:
    st.session_state.uploaded_file_processed = True
