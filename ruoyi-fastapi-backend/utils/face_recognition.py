import os
import cv2
import numpy as np
import face_recognition
from typing import List, Tuple, Dict, Optional
from config import settings
from utils.log_util import logger
from utils.upload_util import UploadUtil


class FaceRecognitionService:
    def __init__(self, model: str = "hog", tolerance: float = 0.6):
        """
        初始化人脸识别服务
        :param model: 人脸检测模型 (hog/cnn)
        :param tolerance: 人脸匹配阈值 (0.6为推荐值)
        """
        self.model = model
        self.tolerance = tolerance
        self.gpu_available = self._check_gpu_support()

        if self.gpu_available and model == "cnn":
            logger.info("GPU加速已启用 - 使用CNN模型")
        else:
            if model == "cnn":
                logger.warning("未检测到GPU支持，自动切换到HOG模型")
                self.model = "hog"

    def _check_gpu_support(self) -> bool:
        """检查系统是否支持GPU加速"""
        try:
            import dlib
            return dlib.DLIB_USE_CUDA
        except:
            return False

    def detect_faces(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        检测图像中的人脸位置
        :param image: numpy数组格式的图像
        :return: 人脸位置列表 [(top, right, bottom, left)]
        """
        try:
            # 性能优化：小图像使用1次上采样，大图像使用2次
            upsample = 1 if max(image.shape) < 1000 else 2

            return face_recognition.face_locations(
                image,
                number_of_times_to_upsample=upsample,
                model=self.model
            )
        except Exception as e:
            logger.error(f"人脸检测失败: {str(e)}")
            return []

    def extract_encodings(self, image: np.ndarray, face_locations: List = None) -> List[np.ndarray]:
        """
        提取人脸特征编码 (128维向量)
        :param image: numpy数组格式的图像
        :param face_locations: 可选的人脸位置列表
        :return: 128维特征向量列表
        """
        try:
            return face_recognition.face_encodings(
                image,
                known_face_locations=face_locations,
                num_jitters=2  # 增加采样提高准确性
            )
        except Exception as e:
            logger.error(f"特征提取失败: {str(e)}")
            return []

    def compare_faces(self, known_encodings: List[np.ndarray], unknown_encoding: np.ndarray) -> bool:
        """
        比对人脸特征
        :param known_encodings: 已知人脸编码列表
        :param unknown_encoding: 待比对的人脸编码
        :return: 是否匹配
        """
        if not known_encodings:
            return False

        results = face_recognition.compare_faces(
            known_encodings,
            unknown_encoding,
            tolerance=self.tolerance
        )
        return any(results)

    def find_best_match(self, known_encodings: List[np.ndarray], unknown_encoding: np.ndarray) -> Tuple[int, float]:
        """
        查找最佳匹配的人脸
        :param known_encodings: 已知人脸编码列表
        :param unknown_encoding: 待比对的人脸编码
        :return: (匹配索引, 相似度)
        """
        if not known_encodings:
            return -1, 0.0

        # 计算欧氏距离 (距离越小越相似)
        face_distances = face_recognition.face_distance(
            known_encodings,
            unknown_encoding
        )
        best_match_index = np.argmin(face_distances)
        similarity = 1 - face_distances[best_match_index]  # 转换为相似度百分比

        return best_match_index, similarity

    def process_image_file(self, file_path: str) -> List[np.ndarray]:
        """
        处理图像文件并提取人脸编码
        :param file_path: 图像文件路径
        :return: 人脸编码列表
        """
        try:
            # 加载图像
            image = face_recognition.load_image_file(file_path)

            # 检测人脸位置
            face_locations = self.detect_faces(image)
            if not face_locations:
                logger.warning(f"未检测到人脸: {file_path}")
                return []

            # 提取特征编码
            return self.extract_encodings(image, face_locations)
        except Exception as e:
            logger.error(f"文件处理失败: {file_path}, 错误: {str(e)}")
            return []

    def process_image_from_url(self, image_url: str) -> List[np.ndarray]:
        """
        从URL加载图像并提取人脸编码
        :param image_url: 图像URL
        :return: 人脸编码列表
        """
        try:
            import requests
            from io import BytesIO

            # 下载图像
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()

            # 转换为numpy数组
            image_data = np.frombuffer(response.content, np.uint8)
            image = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # 检测并提取特征
            face_locations = self.detect_faces(rgb_image)
            return self.extract_encodings(rgb_image, face_locations)
        except Exception as e:
            logger.error(f"URL图像处理失败: {image_url}, 错误: {str(e)}")
            return []

    def process_frame(self, frame: np.ndarray) -> Tuple[List, List]:
        """
        处理视频帧
        :param frame: BGR格式的视频帧
        :return: (人脸位置列表, 人脸编码列表)
        """
        try:
            # 转换为RGB格式 (face_recognition需要)
            rgb_frame = frame[:, :, ::-1]

            # 检测人脸位置
            face_locations = self.detect_faces(rgb_frame)
            if not face_locations:
                return [], []

            # 提取人脸编码
            face_encodings = self.extract_encodings(rgb_frame, face_locations)
            return face_locations, face_encodings
        except Exception as e:
            logger.error(f"视频帧处理失败: {str(e)}")
            return [], []

    def register_face(self, image: np.ndarray, user_id: int) -> Tuple[bool, str]:
        """
        注册人脸并保存特征
        :param image: 包含人脸的图像 (RGB格式)
        :param user_id: 用户ID
        :return: (是否成功, 人脸图片路径)
        """
        try:
            # 检测人脸位置
            face_locations = self.detect_faces(image)
            if not face_locations:
                return False, "未检测到人脸"

            # 提取特征编码
            face_encodings = self.extract_encodings(image, face_locations)
            if not face_encodings:
                return False, "特征提取失败"

            # 保存人脸图片
            face_image_path = self._save_face_image(image, face_locations[0], user_id)
            return True, face_image_path
        except Exception as e:
            logger.error(f"人脸注册失败: {str(e)}")
            return False, f"注册失败: {str(e)}"

    def _save_face_image(self, image: np.ndarray, face_location: Tuple, user_id: int) -> str:
        """保存裁剪后的人脸图片"""
        top, right, bottom, left = face_location
        face_img = image[top:bottom, left:right]

        # 生成保存路径
        save_dir = os.path.join(settings.UPLOAD_DIR, "faces")
        os.makedirs(save_dir, exist_ok=True)
        filename = f"face_{user_id}_{int(time.time())}.jpg"
        save_path = os.path.join(save_dir, filename)

        # 保存图片 (质量90%)
        cv2.imwrite(save_path, cv2.cvtColor(face_img, cv2.COLOR_RGB2BGR),
                    [int(cv2.IMWRITE_JPEG_QUALITY), 90])

        return f"/uploads/faces/{filename}"

    def recognize_faces_in_frame(
            self,
            frame: np.ndarray,
            known_encodings: List[np.ndarray],
            known_user_ids: List[int]
    ) -> List[Dict]:
        """
        在视频帧中识别人脸
        :param frame: BGR格式的视频帧
        :param known_encodings: 已知人脸编码列表
        :param known_user_ids: 对应的用户ID列表
        :return: 识别结果列表 [{'user_id': int, 'location': tuple, 'similarity': float}]
        """
        # 处理视频帧
        face_locations, face_encodings = self.process_frame(frame)
        results = []

        # 比对待识别人脸
        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            user_id = None
            similarity = 0.0

            if known_encodings:
                best_match_index, similarity = self.find_best_match(
                    known_encodings, face_encoding
                )

                if similarity >= self.tolerance:
                    user_id = known_user_ids[best_match_index]

            results.append({
                'location': (left, top, right, bottom),
                'user_id': user_id,
                'similarity': round(similarity * 100, 2)  # 转换为百分比
            })

        return results

    def generate_face_signature(self, encoding: np.ndarray) -> str:
        """
        生成人脸特征签名 (用于数据库存储)
        :param encoding: 128维人脸编码
        :return: Base64编码的字符串
        """
        try:
            import base64
            return base64.b64encode(encoding.tobytes()).decode('utf-8')
        except Exception as e:
            logger.error(f"生成特征签名失败: {str(e)}")
            return ""

    def parse_face_signature(self, signature: str) -> np.ndarray:
        """
        从Base64签名解析人脸编码
        :param signature: Base64编码的字符串
        :return: 128维人脸编码
        """
        try:
            import base64
            decoded = base64.b64decode(signature)
            return np.frombuffer(decoded, dtype=np.float64)
        except Exception as e:
            logger.error(f"解析特征签名失败: {str(e)}")
            return np.array([])


# 全局实例 (单例模式)
face_service = FaceRecognitionService(
    model=settings.FACE_MODEL,
    tolerance=settings.FACE_TOLERANCE
)