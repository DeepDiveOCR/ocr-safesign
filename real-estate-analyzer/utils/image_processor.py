import cv2
import numpy as np
import os

def enhance_image_for_ocr(image_path, output_path="enhanced_image.png"):
    """이미지 비율을 먼저 확인하여 90도 회전 여부를 결정하는 최종 로직"""
    print(f"--- '{os.path.basename(image_path)}' 이미지 전처리 시작 ---")
    img = cv2.imread(image_path)
    
    if img is None: 
        print(f"⚠️ 파일을 읽을 수 없습니다: {image_path}")
        return None, None

    # === 1단계: 이미지 비율로 큰 방향 잡기 ===
    (h, w) = img.shape[:2]
    
    # 가로(w)가 세로(h)보다 길면, 90도 회전이 필요한 문서로 간주합니다.
    if w > h:
        print(f"✅ 가로로 긴 이미지(w:{w}, h:{h}) 감지. 90도 회전 실행.")
        # 원본 이미지를 시계 방향으로 90도 회전시켜 세웁니다.
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    else:
        print(f"✅ 세로로 긴 이미지(w:{w}, h:{h}) 감지. 90도 회전 안함.")

    # 이제 img 변수에는 무조건 세로 방향으로 정렬된 이미지가 들어있습니다.
    # === 2단계: 세로로 정렬된 이미지에서 미세 기울기 보정 ===
    
    # 2단계의 나머지 로직은 이전과 거의 동일합니다.
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    rotated = img.copy() # 최종 결과물을 담을 변수 초기화

    try:
        gray_inv = cv2.bitwise_not(gray)
        _, thresh = cv2.threshold(gray_inv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        coords = np.column_stack(np.where(thresh > 0))
        rect = cv2.minAreaRect(coords)
        angle = rect[-1]
        
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        # 미세조정 각도가 너무 크면 (보통 0에 가까움) 건너뛰는 안전장치는 유지합니다.
        if abs(angle) > 45:
            print(f"⚠️ 미세조정 각도({angle:.2f}°)가 너무 커서 추가 회전은 건너뜁니다.")
            rotated = img.copy()
        else:
            print(f"✅ 미세 기울기 보정 시작 (감지된 각도: {angle:.2f}°)")
            
            (h, w) = img.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            
            cos = np.abs(M[0, 0])
            sin = np.abs(M[0, 1])
            new_w = int((h * sin) + (w * cos))
            new_h = int((h * cos) + (w * sin))
            
            M[0, 2] += (new_w / 2) - center[0]
            M[1, 2] += (new_h / 2) - center[1]
            
            rotated = cv2.warpAffine(img, M, (new_w, new_h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            print(f"✅ 미세 기울기 보정 완료.")
            
    except Exception as e:
        print(f"⚠️ 미세 기울기 보정 중 오류 발생 (90도 회전 원본만 사용): {e}")
        rotated = img.copy() 

    # 최종적으로 노이즈 제거 및 이진화 처리
    final_gray = cv2.cvtColor(rotated, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(final_gray, None, 10, 7, 21)
    final_img = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    
    filename, ext = os.path.splitext(output_path)
    if not ext:
        output_path = filename + '.png'

    cv2.imwrite(output_path, final_img)
    print(f"✅ 전처리 완료, 결과 저장: '{output_path}'")
    return output_path, rotated