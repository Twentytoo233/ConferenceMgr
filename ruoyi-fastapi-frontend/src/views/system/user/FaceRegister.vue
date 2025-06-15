<template>
  <div class="app-container">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span class="title">人脸信息注册</span>
          <el-tag v-if="faceRegistered" type="success" size="small">已注册</el-tag>
          <el-tag v-else type="danger" size="small">未注册</el-tag>
        </div>
      </template>

      <!-- 注册方式选择 -->
      <el-tabs v-model="activeTab" class="register-tabs">
        <el-tab-pane label="摄像头注册" name="camera">
          <div class="camera-section">
            <!-- 摄像头预览 -->
            <div class="camera-preview-wrapper">
              <video
                ref="videoElement"
                class="camera-preview"
                :class="{ 'border-success': capturedImage }"
                autoplay
                playsinline
                muted
              ></video>

              <canvas ref="canvasElement" class="capture-canvas" style="display: none;"></canvas>

              <div v-if="capturedImage" class="capture-result">
                <el-image
                  :src="capturedImage"
                  fit="cover"
                  class="result-image"
                />
              </div>
            </div>

            <!-- 摄像头控制 -->
            <div class="camera-controls">
              <el-button
                type="primary"
                plain
                :icon="VideoPlay"
                @click="startCamera"
                :disabled="cameraActive || faceRegistered"
                size="large"
              >
                启动摄像头
              </el-button>

              <el-button
                type="success"
                :icon="Camera"
                @click="capture"
                :disabled="!cameraActive"
                size="large"
              >
                拍照
              </el-button>

              <el-button
                type="danger"
                plain
                :icon="SwitchButton"
                @click="stopCamera"
                :disabled="!cameraActive"
                size="large"
              >
                关闭摄像头
              </el-button>

              <el-button
                type="warning"
                :icon="Refresh"
                @click="retryCapture"
                :disabled="!capturedImage"
                size="large"
              >
                重新拍摄
              </el-button>
            </div>

            <!-- 注册按钮 -->
            <div class="register-action">
              <el-button
                type="success"
                :icon="Check"
                @click="registerFace"
                :disabled="!capturedImage || faceRegistered"
                size="large"
              >
                确认注册
              </el-button>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="图片上传注册" name="upload">
          <div class="upload-section">
            <!-- 上传区域 -->
            <el-upload
              class="avatar-uploader"
              action=""
              :show-file-list="false"
              :auto-upload="false"
              :on-change="handleFileChange"
              :before-upload="beforeAvatarUpload"
              accept="image/*"
              :disabled="faceRegistered"
            >
              <el-image v-if="uploadedImage" :src="uploadedImage" class="avatar" />
              <el-icon v-else class="avatar-uploader-icon">
                <Plus />
              </el-icon>

              <template #tip>
                <div class="el-upload__tip">
                  上传清晰正面人脸照片<br>
                  (支持 JPG/PNG 格式，大小不超过 2MB)
                </div>
              </template>
            </el-upload>

            <!-- 图片质量检测 -->
            <div v-if="uploadedImage" class="image-quality">
              <el-alert
                v-if="imageQuality === 'good'"
                title="图片质量良好"
                type="success"
                show-icon
                :closable="false"
              />
              <el-alert
                v-else-if="imageQuality === 'medium'"
                title="图片质量中等，建议重新拍摄"
                type="warning"
                show-icon
                :closable="false"
              />
              <el-alert
                v-else
                title="图片质量较差，无法识别"
                type="error"
                show-icon
                :closable="false"
              />
            </div>

            <!-- 操作按钮 -->
            <div class="upload-actions">
              <el-button
                type="success"
                :icon="Check"
                @click="registerFromFile"
                :disabled="!uploadedImage || faceRegistered || imageQuality === 'poor'"
                size="large"
              >
                确认注册
              </el-button>

              <el-button
                type="warning"
                :icon="Delete"
                @click="clearUpload"
                :disabled="!uploadedImage"
                size="large"
              >
                重新选择
              </el-button>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>

      <!-- 注册要求提示 -->
      <el-alert
        title="注册要求"
        type="info"
        show-icon
        :closable="false"
        class="quality-tips"
      >
        <ul>
          <li>请保持面部在光线充足的环境下</li>
          <li>正对摄像头，保持面部无遮挡</li>
          <li>避免戴帽子、口罩等遮挡物</li>
          <li>照片清晰度不低于720p</li>
          <li>确保面部占据图片主要区域</li>
        </ul>
      </el-alert>
    </el-card>

    <!-- 已注册人脸信息展示 -->
    <el-card v-if="faceRegistered" class="box-card registered-card">
      <template #header>
        <div class="card-header">
          <span class="title">已注册人脸信息</span>
          <el-button
            type="danger"
            size="small"
            @click="deleteFace"
            :icon="Delete"
          >
            删除注册信息
          </el-button>
        </div>
      </template>

      <div class="registered-face">
        <el-image
          :src="registeredFaceImage"
          class="registered-image"
          fit="cover"
        />

        <div class="face-info">
          <div class="info-item">
            <span class="info-label">注册时间：</span>
            <span class="info-value">{{ registeredTime }}</span>
          </div>

          <div class="info-item">
            <span class="info-label">人脸质量：</span>
            <el-rate
              v-model="faceQuality"
              disabled
              :colors="['#99A9BF', '#F7BA2A', '#FF9900']"
              :texts="['差', '中', '良', '优', '完美']"
              show-text
            />
          </div>

          <div class="info-item">
            <span class="info-label">状态：</span>
            <el-tag :type="faceStatusType" size="large">
              {{ faceStatusText }}
            </el-tag>
          </div>

          <div class="info-item">
            <span class="info-label">最后使用：</span>
            <span class="info-value">{{ lastUsedTime || '尚未使用' }}</span>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import {
  VideoPlay, Camera, SwitchButton, Refresh,
  Check, Delete, Plus
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/store/user'
import {
  getFaceInfo,
  registerFace,
  deleteFace,
  uploadFaceImage
} from '@/api/system/user'

const userStore = useUserStore()

// 摄像头相关
const videoElement = ref(null)
const canvasElement = ref(null)
const cameraActive = ref(false)
const capturedImage = ref(null)
const stream = ref(null)

// 上传相关
const uploadedImage = ref(null)
const imageQuality = ref(null) // good, medium, poor

// 人脸信息
const faceRegistered = ref(false)
const registeredFaceImage = ref('')
const registeredTime = ref('')
const lastUsedTime = ref('')
const faceQuality = ref(3) // 1-5分

// 其他状态
const activeTab = ref('camera')

// 计算属性
const faceStatusType = computed(() => {
  return faceQuality.value >= 4 ? 'success' :
         faceQuality.value >= 3 ? 'warning' : 'danger'
})

const faceStatusText = computed(() => {
  return faceQuality.value >= 4 ? '优质' :
         faceQuality.value >= 3 ? '合格' : '需重新注册'
})

// 初始化时获取人脸注册状态
onMounted(async () => {
  await fetchFaceInfo()
})

// 组件卸载前关闭摄像头
onBeforeUnmount(() => {
  stopCamera()
})

// 获取人脸注册信息
const fetchFaceInfo = async () => {
  try {
    const res = await getFaceInfo(userStore.userId)
    if (res.code === 200 && res.data) {
      faceRegistered.value = true
      registeredFaceImage.value = res.data.faceImagePath
        ? `${import.meta.env.VITE_APP_BASE_API}${res.data.faceImagePath}?t=${Date.now()}`
        : ''
      registeredTime.value = res.data.registerTime || ''
      lastUsedTime.value = res.data.lastUsedTime || ''
      faceQuality.value = res.data.quality || 3
    } else {
      faceRegistered.value = false
    }
  } catch (error) {
    console.error('获取人脸信息失败:', error)
    ElMessage.error('获取人脸信息失败，请稍后重试')
    faceRegistered.value = false
  }
}

// 启动摄像头
const startCamera = async () => {
  try {
    // 停止之前可能的摄像头
    if (stream.value) {
      stopCamera()
    }

    // 获取摄像头权限
    const constraints = {
      video: {
        width: { ideal: 1280 },
        height: { ideal: 720 },
        facingMode: 'user'
      }
    }

    stream.value = await navigator.mediaDevices.getUserMedia(constraints)
    videoElement.value.srcObject = stream.value
    cameraActive.value = true
    capturedImage.value = null

  } catch (error) {
    console.error('摄像头启动失败:', error)
    let errorMsg = '无法访问摄像头'

    if (error.name === 'NotAllowedError') {
      errorMsg = '摄像头访问被拒绝，请检查浏览器权限设置'
    } else if (error.name === 'NotFoundError') {
      errorMsg = '未找到可用的摄像头设备'
    } else if (error.name === 'NotReadableError') {
      errorMsg = '摄像头被占用，请关闭其他使用摄像头的应用'
    }

    ElMessage.error(errorMsg)
  }
}

// 停止摄像头
const stopCamera = () => {
  if (stream.value) {
    stream.value.getTracks().forEach(track => {
      track.stop()
    })
    stream.value = null
  }
  cameraActive.value = false
}

// 拍照
const capture = () => {
  const video = videoElement.value
  const canvas = canvasElement.value
  const context = canvas.getContext('2d')

  // 设置画布尺寸
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight

  // 绘制图像
  context.drawImage(video, 0, 0, canvas.width, canvas.height)

  // 转换为DataURL
  capturedImage.value = canvas.toDataURL('image/jpeg', 0.9)
}

// 重新拍摄
const retryCapture = () => {
  capturedImage.value = null
}

// 处理文件上传
const handleFileChange = (file) => {
  const reader = new FileReader()
  reader.onload = (e) => {
    uploadedImage.value = e.target.result
    checkImageQuality(file.raw)
  }
  reader.readAsDataURL(file.raw)
}

// 检查图片质量（模拟）
const checkImageQuality = (file) => {
  // 这里实际项目中应该调用API或本地算法检测图片质量
  // 这里简单模拟：文件大于500KB为优质，200-500KB中等，小于200KB差
  if (file.size > 500 * 1024) {
    imageQuality.value = 'good'
  } else if (file.size > 200 * 1024) {
    imageQuality.value = 'medium'
  } else {
    imageQuality.value = 'poor'
  }
}

// 清除上传的文件
const clearUpload = () => {
  uploadedImage.value = null
  imageQuality.value = null
}

// 上传前检查
const beforeAvatarUpload = (file) => {
  const isImage = file.type.startsWith('image/')
  const isLt2M = file.size / 1024 / 1024 < 2

  if (!isImage) {
    ElMessage.error('只能上传图片文件!')
    return false
  }

  if (!isLt2M) {
    ElMessage.error('图片大小不能超过 2MB!')
    return false
  }

  return true
}

// 注册人脸（从摄像头）
const registerFace = async () => {
  if (!capturedImage.value) {
    ElMessage.warning('请先拍照')
    return
  }

  try {
    // 将DataURL转换为Blob
    const blob = await dataURLToBlob(capturedImage.value)

    // 创建FormData
    const formData = new FormData()
    formData.append('image', blob, `face_${userStore.userId}.jpg`)
    formData.append('userId', userStore.userId)

    // 调用注册API
    const res = await registerFace(formData)

    if (res.code === 200) {
      ElMessage.success('人脸注册成功')

      // 更新本地状态
      await fetchFaceInfo()

      // 关闭摄像头
      stopCamera()

      // 重置状态
      capturedImage.value = null
    } else {
      ElMessage.error(res.msg || '注册失败')
    }
  } catch (error) {
    console.error('注册失败:', error)
    ElMessage.error(`人脸注册失败: ${error.message || '未知错误'}`)
  }
}

// 注册人脸（从文件）
const registerFromFile = async () => {
  if (!uploadedImage.value) {
    ElMessage.warning('请先上传照片')
    return
  }

  try {
    // 将DataURL转换为Blob
    const blob = await dataURLToBlob(uploadedImage.value)

    // 创建FormData
    const formData = new FormData()
    formData.append('image', blob, `face_${userStore.userId}_upload.jpg`)
    formData.append('userId', userStore.userId)

    // 调用注册API
    const res = await registerFace(formData)

    if (res.code === 200) {
      ElMessage.success('人脸注册成功')

      // 更新本地状态
      await fetchFaceInfo()

      // 重置状态
      uploadedImage.value = null
      imageQuality.value = null
    } else {
      ElMessage.error(res.msg || '注册失败')
    }
  } catch (error) {
    console.error('注册失败:', error)
    ElMessage.error(`人脸注册失败: ${error.message || '未知错误'}`)
  }
}

// 删除人脸信息
const deleteFace = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要删除人脸注册信息吗？删除后将无法使用人脸签到功能',
      '警告',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    )

    const res = await deleteFace(userStore.userId)
    if (res.code === 200) {
      ElMessage.success('人脸信息已删除')

      // 更新本地状态
      faceRegistered.value = false
      registeredFaceImage.value = ''
    } else {
      ElMessage.error(res.msg || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error(`删除失败: ${error.message || '未知错误'}`)
    }
  }
}

// 工具函数：将DataURL转换为Blob
const dataURLToBlob = (dataURL) => {
  return new Promise((resolve) => {
    const arr = dataURL.split(',')
    const mime = arr[0].match(/:(.*?);/)[1]
    const bstr = atob(arr[1])
    let n = bstr.length
    const u8arr = new Uint8Array(n)

    while (n--) {
      u8arr[n] = bstr.charCodeAt(n)
    }

    resolve(new Blob([u8arr], { type: mime }))
  })
}
</script>

<style scoped lang="scss">
.app-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.box-card {
  margin-bottom: 20px;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;

    .title {
      font-size: 18px;
      font-weight: 600;
      color: #303133;
    }
  }
}

.register-tabs {
  margin: 0 20px;

  :deep(.el-tabs__header) {
    margin-bottom: 24px;
  }

  :deep(.el-tabs__item) {
    font-size: 16px;
    font-weight: 500;
  }
}

.camera-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
  padding: 0 20px 20px;

  .camera-preview-wrapper {
    position: relative;
    width: 100%;
    max-width: 700px;
    height: 400px;
    background-color: #f8f9fa;
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid #ebeef5;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);

    .camera-preview {
      width: 100%;
      height: 100%;
      object-fit: cover;
      background-color: #000;
      transition: all 0.3s ease;

      &.border-success {
        border: 3px solid #67c23a;
      }
    }

    .capture-result {
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      z-index: 10;
      background: #fff;

      .result-image {
        width: 100%;
        height: 100%;
        border-radius: 12px;
      }
    }
  }

  .camera-controls {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 16px;
    width: 100%;

    .el-button {
      min-width: 140px;
      font-weight: 500;
    }
  }

  .register-action {
    margin-top: 10px;

    .el-button {
      min-width: 200px;
      height: 48px;
      font-size: 16px;
      font-weight: 500;
    }
  }
}

.upload-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
  padding: 0 20px 20px;

  .avatar-uploader {
    width: 100%;
    max-width: 500px;
    height: 350px;
    border: 2px dashed #dcdfe6;
    border-radius: 12px;
    cursor: pointer;
    position: relative;
    overflow: hidden;
    display: flex;
    justify-content: center;
    align-items: center;
    background-color: #f8f9fa;
    transition: border-color 0.3s;

    &:hover {
      border-color: #409eff;
    }

    .avatar-uploader-icon {
      font-size: 48px;
      color: #8c939d;
    }

    .avatar {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
  }

  .el-upload__tip {
    margin-top: 16px;
    text-align: center;
    color: #606266;
    font-size: 14px;
    line-height: 1.6;
  }

  .image-quality {
    width: 100%;
    max-width: 500px;
  }

  .upload-actions {
    display: flex;
    justify-content: center;
    gap: 20px;
    width: 100%;

    .el-button {
      min-width: 160px;
      height: 48px;
      font-size: 16px;
      font-weight: 500;
    }
  }
}

.quality-tips {
  margin: 20px 0;
  border-radius: 8px;

  ul {
    margin: 10px 0 0 24px;
    padding: 0;

    li {
      margin-bottom: 8px;
      color: #606266;
      font-size: 14px;
      line-height: 1.6;
    }
  }
}

.registered-card {
  .card-header {
    border-bottom: 1px solid #ebeef5;
  }

  .registered-face {
    display: flex;
    flex-wrap: wrap;
    gap: 30px;
    padding: 20px;

    .registered-image {
      width: 240px;
      height: 300px;
      border-radius: 12px;
      border: 1px solid #ebeef5;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    }

    .face-info {
      flex: 1;
      min-width: 300px;

      .info-item {
        display: flex;
        align-items: center;
        margin-bottom: 24px;
        font-size: 16px;

        .info-label {
          display: inline-block;
          width: 100px;
          color: #606266;
          font-weight: 500;
        }

        .info-value {
          color: #303133;
          font-weight: 500;
        }

        .el-rate {
          margin-top: 4px;
        }
      }
    }
  }
}

@media (max-width: 768px) {
  .camera-section {
    .camera-preview-wrapper {
      height: 300px;
    }

    .camera-controls {
      flex-direction: column;
      align-items: center;

      .el-button {
        width: 100%;
        max-width: 300px;
      }
    }
  }

  .registered-face {
    flex-direction: column;

    .registered-image {
      width: 100% !important;
      max-width: 300px;
      margin: 0 auto;
    }

    .face-info {
      width: 100%;
      min-width: unset !important;
    }
  }
}
</style>