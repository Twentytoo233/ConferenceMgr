<template>
  <div class="app-container">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span class="title">人脸信息注册</span>
          <el-tag type="success" v-if="faceRegistered">已注册</el-tag>
          <el-tag type="danger" v-else>未注册</el-tag>
        </div>
      </template>

      <div class="flex-container">
        <!-- 摄像头注册区域 -->
        <div class="camera-section">
          <div class="camera-box">
            <video ref="videoElement" class="camera-preview" autoplay playsinline muted></video>
            <canvas ref="canvasElement" class="capture-canvas" style="display: none;"></canvas>
          </div>

          <div class="camera-controls">
            <el-button
              type="primary"
              @click="startCamera"
              :disabled="cameraActive"
              icon="VideoPlay"
            >
              启动摄像头
            </el-button>
            <el-button
              type="success"
              @click="capture"
              :disabled="!cameraActive"
              icon="Camera"
            >
              拍照
            </el-button>
            <el-button
              type="danger"
              @click="stopCamera"
              :disabled="!cameraActive"
              icon="VideoPause"
            >
              关闭摄像头
            </el-button>
          </div>

          <div class="capture-result" v-if="capturedImage">
            <el-image :src="capturedImage" fit="cover" class="result-image" />
            <div class="result-actions">
              <el-button type="success" @click="registerFace" icon="Check">确认注册</el-button>
              <el-button type="warning" @click="retryCapture" icon="Refresh">重新拍摄</el-button>
            </div>
          </div>
        </div>

        <!-- 上传注册区域 -->
        <div class="divider">
          <div class="or-divider">或</div>
        </div>

        <div class="upload-section">
          <el-upload
            class="avatar-uploader"
            action=""
            :show-file-list="false"
            :auto-upload="false"
            :on-change="handleFileChange"
            accept="image/*"
          >
            <el-image v-if="uploadedImage" :src="uploadedImage" class="avatar" />
            <el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>

            <template #tip>
              <div class="el-upload__tip">
                上传清晰正面人脸照片<br>
                (支持jpg/png格式)
              </div>
            </template>
          </el-upload>

          <div v-if="uploadedImage" class="upload-actions">
            <el-button type="success" @click="registerFromFile" icon="Check">确认注册</el-button>
            <el-button type="warning" @click="clearUpload" icon="Delete">重新选择</el-button>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 人脸质量提示 -->
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
      </ul>
    </el-alert>

    <!-- 已注册人脸展示 -->
    <el-card class="box-card" v-if="faceRegistered">
      <template #header>
        <div class="card-header">
          <span class="title">已注册人脸信息</span>
          <el-button type="danger" size="small" @click="deleteFace" icon="Delete">删除注册信息</el-button>
        </div>
      </template>

      <div class="registered-face">
        <el-image :src="registeredFaceImage" class="registered-image" fit="cover" />
        <div class="face-info">
          <p><span class="info-label">注册时间：</span>{{ registeredTime }}</p>
          <p><span class="info-label">人脸质量：</span>
            <el-rate
              v-model="faceQuality"
              disabled
              :colors="['#99A9BF', '#F7BA2A', '#FF9900']"
            />
          </p>
          <p><span class="info-label">状态：</span>
            <el-tag :type="faceStatusType">{{ faceStatusText }}</el-tag>
          </p>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getFaceInfo, registerFace, deleteFace } from '@/api/system/user'
import { baseURL } from '@/utils/request'

const videoElement = ref(null)
const canvasElement = ref(null)
const cameraActive = ref(false)
const capturedImage = ref(null)
const uploadedImage = ref(null)
const faceRegistered = ref(false)
const registeredFaceImage = ref('')
const registeredTime = ref('')
const faceQuality = ref(3)
const stream = ref(null)

// 用户信息（实际应用中从store或props获取）
const userInfo = ref({
  userId: 10001,
  userName: '张三',
  deptName: '技术研发部'
})

// 计算属性
const faceStatusType = computed(() => {
  return faceQuality.value >= 4 ? 'success' :
         faceQuality.value >= 2 ? 'warning' : 'danger'
})

const faceStatusText = computed(() => {
  return faceQuality.value >= 4 ? '优质' :
         faceQuality.value >= 2 ? '合格' : '需重新注册'
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
    const res = await getFaceInfo(userInfo.value.userId)
    if (res.code === 200) {
      faceRegistered.value = true
      registeredFaceImage.value = `${baseURL}${res.data.faceImagePath}?t=${Date.now()}`
      registeredTime.value = res.data.registerTime
      faceQuality.value = res.data.quality || 3
    } else {
      faceRegistered.value = false
    }
  } catch (error) {
    console.error('获取人脸信息失败:', error)
    faceRegistered.value = false
  }
}

// 启动摄像头
const startCamera = async () => {
  try {
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
    ElMessage.error('无法访问摄像头: ' + error.message)
  }
}

// 停止摄像头
const stopCamera = () => {
  if (stream.value) {
    stream.value.getTracks().forEach(track => track.stop())
    stream.value = null
  }
  cameraActive.value = false
}

// 拍照
const capture = () => {
  const video = videoElement.value
  const canvas = canvasElement.value
  const context = canvas.getContext('2d')

  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  context.drawImage(video, 0, 0, canvas.width, canvas.height)

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
  }
  reader.readAsDataURL(file.raw)
}

// 清除上传的文件
const clearUpload = () => {
  uploadedImage.value = null
}

// 注册人脸（从摄像头）
const registerFace = async () => {
  if (!capturedImage.value) {
    ElMessage.warning('请先拍照')
    return
  }

  try {
    const blob = await dataURLToBlob(capturedImage.value)
    const formData = new FormData()
    formData.append('image', blob, 'face.jpg')
    formData.append('userId', userInfo.value.userId)

    const res = await registerFace(formData)
    if (res.code === 200) {
      ElMessage.success('人脸注册成功')
      await fetchFaceInfo()
      stopCamera()
      capturedImage.value = null
    } else {
      ElMessage.error(res.msg || '注册失败')
    }
  } catch (error) {
    console.error('注册失败:', error)
    ElMessage.error('人脸注册失败: ' + error.message)
  }
}

// 注册人脸（从文件）
const registerFromFile = async () => {
  if (!uploadedImage.value) {
    ElMessage.warning('请先上传照片')
    return
  }

  try {
    const blob = await dataURLToBlob(uploadedImage.value)
    const formData = new FormData()
    formData.append('image', blob, 'face_upload.jpg')
    formData.append('userId', userInfo.value.userId)

    const res = await registerFace(formData)
    if (res.code === 200) {
      ElMessage.success('人脸注册成功')
      await fetchFaceInfo()
      uploadedImage.value = null
    } else {
      ElMessage.error(res.msg || '注册失败')
    }
  } catch (error) {
    console.error('注册失败:', error)
    ElMessage.error('人脸注册失败: ' + error.message)
  }
}

// 删除人脸信息
const deleteFace = async () => {
  try {
    await ElMessageBox.confirm('确定要删除人脸注册信息吗？删除后将无法使用人脸签到功能', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    const res = await deleteFace(userInfo.value.userId)
    if (res.code === 200) {
      ElMessage.success('人脸信息已删除')
      faceRegistered.value = false
    } else {
      ElMessage.error(res.msg || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error('删除失败: ' + error.message)
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

<style scoped>
.app-container {
  padding: 20px;
}

.box-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  font-size: 18px;
  font-weight: bold;
}

.flex-container {
  display: flex;
  justify-content: space-between;
  gap: 30px;
}

.camera-section, .upload-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.divider {
  position: relative;
  width: 1px;
  background-color: #ebeef5;
}

.or-divider {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: white;
  padding: 0 10px;
  color: #909399;
  font-size: 14px;
}

.camera-box {
  position: relative;
  width: 100%;
  max-width: 500px;
  background-color: #f5f7fa;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 20px;
}

.camera-preview {
  width: 100%;
  height: 300px;
  object-fit: cover;
  background-color: #000;
}

.capture-canvas {
  width: 100%;
  height: 300px;
}

.camera-controls {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-bottom: 20px;
}

.capture-result {
  width: 100%;
  max-width: 500px;
  text-align: center;
}

.result-image {
  width: 100%;
  height: 300px;
  border-radius: 8px;
  border: 1px solid #ebeef5;
  margin-bottom: 15px;
}

.result-actions {
  display: flex;
  justify-content: center;
  gap: 15px;
}

.avatar-uploader {
  width: 100%;
  max-width: 300px;
  height: 300px;
  border: 1px dashed #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #f5f7fa;
}

.avatar-uploader:hover {
  border-color: #409eff;
}

.avatar-uploader-icon {
  font-size: 28px;
  color: #8c939d;
}

.avatar {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.el-upload__tip {
  margin-top: 10px;
  text-align: center;
  color: #606266;
  font-size: 12px;
  line-height: 1.5;
}

.upload-actions {
  margin-top: 20px;
  display: flex;
  justify-content: center;
  gap: 15px;
}

.quality-tips {
  margin: 20px 0;
}

.quality-tips ul {
  margin: 10px 0 0 20px;
  padding: 0;
}

.quality-tips li {
  margin-bottom: 5px;
}

.registered-face {
  display: flex;
  gap: 30px;
  align-items: center;
}

.registered-image {
  width: 200px;
  height: 250px;
  border-radius: 8px;
  border: 1px solid #ebeef5;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.face-info {
  flex: 1;
}

.face-info p {
  margin-bottom: 20px;
  font-size: 16px;
}

.info-label {
  display: inline-block;
  width: 100px;
  color: #606266;
  font-weight: bold;
}
</style>