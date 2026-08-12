<template>
  <div class="email-content-viewer">
    <!-- 邮件头部信息 -->
    <div class="email-header">
      <div class="header-item subject">
        <h2>{{ mail.subject || '(无主题)' }}</h2>
      </div>

      <div class="header-details">
        <div class="header-item">
          <div class="label">发件人:</div>
          <div class="value sender">
            <el-avatar v-if="senderInitial" :size="24" class="sender-avatar">{{ senderInitial }}</el-avatar>
            <span>{{ mail.sender || '(未知发件人)' }}</span>
          </div>
        </div>

        <div class="header-item" v-if="mail.recipient">
          <div class="label">收件人:</div>
          <div class="value">{{ mail.recipient }}</div>
        </div>

        <div class="header-item" v-if="mail.cc && mail.cc.length > 0">
          <div class="label">抄送:</div>
          <div class="value">{{ mail.cc }}</div>
        </div>

        <div class="header-item">
          <div class="label">时间:</div>
          <div class="value">{{ formatDate(mail.received_time) }}</div>
        </div>

        <div class="header-item" v-if="mail.folder && mail.folder !== 'INBOX'">
          <div class="label">文件夹:</div>
          <div class="value">
            <el-tag size="small" type="info">{{ mail.folder }}</el-tag>
          </div>
        </div>
      </div>
    </div>

    <!-- 附件区域 -->
    <div v-if="hasAttachments" class="email-attachments">
      <div class="attachments-header">
        <el-icon><Paperclip /></el-icon>
        <span>附件 ({{ attachmentsCount }})</span>
      </div>

      <div class="attachments-loading" v-if="loadingAttachments">
        <el-skeleton :rows="1" animated />
      </div>

      <div v-else class="attachments-list">
        <div v-for="attachment in attachments" :key="attachment.id" class="attachment-item">
          <div class="attachment-icon">
            <el-icon v-if="isImageAttachment(attachment)"><Picture /></el-icon>
            <el-icon v-else-if="isPdfAttachment(attachment)"><Document /></el-icon>
            <el-icon v-else-if="isTextAttachment(attachment)"><Reading /></el-icon>
            <el-icon v-else-if="isArchiveAttachment(attachment)"><Files /></el-icon>
            <el-icon v-else><Document /></el-icon>
          </div>

          <div class="attachment-info">
            <div class="attachment-name">{{ attachment.filename }}</div>
            <div class="attachment-size">{{ formatFileSize(attachment.size) }}</div>
          </div>

          <div class="attachment-actions">
            <el-tooltip content="下载附件" placement="top">
              <el-button size="small" type="primary" circle @click="downloadAttachment(attachment.id, attachment.filename)">
                <el-icon><Download /></el-icon>
              </el-button>
            </el-tooltip>

            <el-tooltip v-if="canPreviewAttachment(attachment)" content="预览" placement="top">
              <el-button size="small" type="success" circle @click="previewAttachment(attachment)">
                <el-icon><View /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </div>
      </div>
    </div>

    <!-- 邮件内容 -->
    <div class="email-content">
      <!-- 根据邮件类型选择不同的渲染方式 -->
  <template v-if="isHtmlContent">
        <!-- GitHub邮件特殊处理 -->
        <div v-if="isGitHubEmail" class="github-container">
          <div class="github-header">
            <!-- 使用内联SVG替代外部图片 -->
            <svg class="github-logo" viewBox="0 0 16 16" width="24" height="24" fill="white">
              <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path>
            </svg>
            <span class="github-title">GitHub</span>
          </div>
        <iframe class="html-frame github-email" :srcdoc="sanitizedContent" ref="contentFrame" @load="onFrameLoad" style="height:100%"></iframe>
        </div>
        <!-- Microsoft邮件特殊处理 - 移除顶部标题栏，直接显示内容 -->
        <div v-else-if="isMicrosoftEmail" class="microsoft-container-new">
        <iframe class="html-frame microsoft-email-new" :srcdoc="sanitizedContent" ref="contentFrame" @load="onFrameLoad" style="height:100%"></iframe>
        </div>
        <!-- Notion邮件特殊处理 -->
        <div v-else-if="isNotionEmail" class="notion-container">
          <div class="notion-header">
            <!-- 使用内联SVG替代外部图片 -->
            <svg class="notion-logo" viewBox="0 0 24 24" width="24" height="24" fill="white">
              <path d="M4.459 4.208c.746.606 1.026.56 2.428.466l13.215-.793c.28 0 .047-.28-.046-.326L17.86 1.968c-.42-.326-.981-.7-2.055-.607L3.01 2.295c-.466.046-.56.28-.374.466l1.823 1.447zm1.775 2.22c.746.56.932.606 2.334.513l10.335-.746c.28-.047.327-.14.187-.326l-1.96-1.914c-.374-.28-.934-.606-1.867-.56l-10.8.7c-.327.046-.374.186-.14.373l1.913 1.96zm-1.355 3.9c.7-.327 1.142-.607 2.334-.607l11.126.187c.28.047.374.28.188.466l-.7.56c-.046.047-.093.047-.187.047l-12.318-.233c-.28 0-.42-.093-.374-.28l.187-.14zm17.35 1.12c-.046-.7-.046-1.447-.7-2.334l-.653.187c-.373.933-.7 1.496-1.82 1.914-1.26.466-2.568.28-3.595-.187-1.447-.652-2.986-1.447-4.5-1.027-.84.233-1.54.84-1.96 1.68l-1.073 1.773c-.187.28-.14.653.046.84.7.7 1.307 1.213 1.307 2.334 0 .98-.56 1.727-1.447 2.054-.84.28-1.913.14-2.754-.327-.6-.333-1.167-.667-1.633-1.214-.187-.186-.42-.233-.653-.186l-.7.187c-.046 0-.093.046-.093.093 0 .047 0 .094.046.14.7.933 1.54 1.68 2.708 2.147 1.447.56 3.595.56 4.9-.56 1.307-1.167 1.54-2.94.7-4.387-.28-.466-.56-.933-.84-1.353-.093-.14-.093-.327.047-.42.793-.747 1.773-1.267 2.94-.98 1.167.373 2.241.933 3.362 1.4.933.373 2.055.56 3.082.093 1.213-.513 2.147-1.493 2.334-2.8.093-.933.28-1.867.28-2.8 0-.047-.047-.093-.094-.093l-.046.046z"/>
            </svg>
            <span class="notion-title">Notion</span>
          </div>
        <iframe class="html-frame notion-email" :srcdoc="sanitizedContent" ref="contentFrame" @load="onFrameLoad" style="height:100%"></iframe>
        </div>
        <div v-else class="default-container">
          <iframe class="html-frame default-email" :srcdoc="sanitizedContent" ref="contentFrame" @load="onFrameLoad"></iframe>
        </div>
      </template>
      <!-- 纯文本邮件 -->
      <template v-else-if="isPlainText">
        <pre class="plain-content">{{ processedPlainText }}</pre>
      </template>
      <!-- 其他格式邮件 -->
      <template v-else>
        <div class="unknown-content">
          <p class="warning-text">此邮件格式无法正确显示，请尝试下载原始邮件查看。</p>
          <el-button type="primary" size="small" @click="downloadOriginalEmail">
            <el-icon><Download /></el-icon> 下载原始邮件
          </el-button>
        </div>
      </template>
    </div>

    <!-- 附件预览对话框 -->
    <el-dialog
      v-model="previewDialogVisible"
      :title="previewingAttachment ? previewingAttachment.filename : '附件预览'"
      width="90%"
      destroy-on-close
    >
      <div v-if="previewingAttachment" class="attachment-preview">
        <div v-if="isImageAttachment(previewingAttachment)" class="image-preview">
          <img :src="previewUrl" :alt="previewingAttachment.filename" />
        </div>
        <div v-else-if="isTextAttachment(previewingAttachment)" class="text-preview">
          <pre>{{ previewContent }}</pre>
        </div>
        <div v-else-if="isPdfAttachment(previewingAttachment)" class="pdf-preview">
          <iframe :src="previewUrl" width="100%" height="500"></iframe>
        </div>
        <div v-else class="unsupported-preview">
          <p>无法预览此类型的附件，请下载后查看。</p>
          <el-button type="primary" @click="downloadAttachment(previewingAttachment.id, previewingAttachment.filename)">
            <el-icon><Download /></el-icon> 下载附件
          </el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { Document, Download, View, Picture, Files, Paperclip, Reading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import DOMPurify from 'dompurify'
import dayjs from 'dayjs'

const props = defineProps({
  mail: {
    type: Object,
    required: true
  },
  attachments: {
    type: Array,
    default: () => []
  },
  loadingAttachments: {
    type: Boolean,
    default: false
  }
})

// 附件预览相关
const previewDialogVisible = ref(false)
const previewingAttachment = ref(null)
const previewUrl = ref('')
const previewContent = ref('')

// 计算属性
const mailContent = computed(() => {
  if (!props.mail) return ''

  let content = ''

  // 兼容新旧格式
  if (typeof props.mail.content === 'object' && props.mail.content !== null) {
    content = props.mail.content.content || ''
  } else {
    content = props.mail.content || ''
  }

  // 尝试解析可能是JSON字符串的内容
  if (typeof content === 'string' && content.trim().startsWith('["content":')) {
    try {
      // 提取JSON部分
      const jsonMatch = content.match(/\["content":\s*"(.+?)"\]/s)
      if (jsonMatch && jsonMatch[1]) {
        content = jsonMatch[1]
        // 解码转义的JSON字符串
        content = content
          .replace(/\\"/g, '"')
          .replace(/\\n/g, '\n')
          .replace(/\\r/g, '')
          .replace(/\\t/g, '\t')
          .replace(/\\\\/g, '\\')
      }
    } catch (error) {
      console.error('解析邮件内容JSON失败:', error)
    }
  }

  return content
})

// 处理纯文本邮件中的特殊字符
const processedPlainText = computed(() => {
  if (!mailContent.value) return ''

  let text = mailContent.value

  // 处理特殊字符和转义序列
  text = text
    .replace(/\\n/g, '\n')
    .replace(/\\r/g, '')
    .replace(/\\t/g, '    ')
    .replace(/\\\\/g, '\\')
    .replace(/\\'/g, "'")
    .replace(/\\"/g, '"')
    .replace(/\n\n+/g, '\n\n') // 合并多个连续换行

  // 处理UTF-8编码问题
  try {
    // 尝试检测是否有编码问题的字符
    if (text.includes('Ã') || text.includes('Â')) {
      // 尝试修复UTF-8编码问题
      const decoder = new TextDecoder('utf-8')
      const encoder = new TextEncoder()
      const bytes = encoder.encode(text)
      text = decoder.decode(bytes)
    }
  } catch (error) {
    console.error('处理文本编码失败:', error)
  }

  return text
})

// 检查是否是HTML内容
const isHtmlContent = computed(() => {
  if (!props.mail || !props.mail.content) return false

  // 兼容新旧格式
  if (typeof props.mail.content === 'object') {
    return props.mail.content.has_html === true ||
           props.mail.content.content_type === 'text/html' ||
           props.mail.content.content_type?.includes('html')
  }

  // 旧格式，检查内容是否包含HTML标签
  const content = String(props.mail.content || '')
  return content.includes('<html') || content.includes('<body') ||
         content.includes('<div') || content.includes('<p>') ||
         content.includes('<table') || content.includes('<img') ||
         content.includes('<a ') || content.includes('<br') ||
         content.includes('<style') || content.includes('<span')
})

// 在邮件内容渲染后修复垂直排列的文本和其他格式问题
const fixVerticalText = () => {
  // 等待DOM更新完成
  setTimeout(() => {
    try {
      // 查找所有可能包含垂直文本的元素
      const contentContainer = document.querySelector('.email-content');
      if (!contentContainer) return;

      // 检查是否是微软邮件，针对微软邮件做特殊处理
      const isMicrosoft = contentContainer.querySelector('.microsoft-email');

      // 处理表格单元格
      const cells = contentContainer.querySelectorAll('td, th');
      cells.forEach(cell => {
        const text = cell.textContent.trim();
        // 检查是否是垂直排列的文本
        if (text.length > 5 && (cell.offsetWidth < 30 ||
            (cell.getAttribute('width') && parseInt(cell.getAttribute('width')) < 30) ||
            (cell.style.width && parseInt(cell.style.width) < 30))) {
          cell.style.minWidth = '100px';
          cell.style.width = 'auto';
          cell.style.whiteSpace = 'normal';
          cell.style.wordBreak = 'break-word';
          cell.style.wordWrap = 'break-word';

          // 移除可能导致问题的属性
          if (cell.hasAttribute('width')) {
            cell.removeAttribute('width');
          }
          if (cell.hasAttribute('nowrap')) {
            cell.removeAttribute('nowrap');
          }
        }

        // 强制单元格内容自动换行
        cell.style.whiteSpace = 'normal';
        cell.style.wordBreak = 'break-word';
      });

      // 处理表格
      const tables = contentContainer.querySelectorAll('table');
      tables.forEach(table => {
        // 移除表格边框，使用更简洁的样式
        table.style.borderCollapse = 'collapse';
        table.style.width = '100%';
        table.style.maxWidth = '100%';
        table.style.margin = '16px auto';

        // 如果表格有border属性，设置为0
        if (table.hasAttribute('border')) {
          table.setAttribute('border', '0');
        }

        // 移除可能导致问题的属性
        if (table.hasAttribute('width')) {
          table.removeAttribute('width');
        }
      });

      // 处理div容器
      const divs = contentContainer.querySelectorAll('div');
      divs.forEach(div => {
        // 检查是否是窄列布局
        if (div.offsetWidth < 50 && div.offsetHeight > 100) {
          div.style.width = 'auto';
          div.style.minWidth = '200px';
          div.style.maxWidth = '100%';
        }

        // 检查是否有固定宽度
        const computedStyle = window.getComputedStyle(div);
        const width = computedStyle.getPropertyValue('width');
        if (width.endsWith('px')) {
          const numWidth = parseInt(width);
          if (numWidth < 50) {
            div.style.width = 'auto';
            div.style.minWidth = '200px';
          }
        }

        // 检查是否有固定宽度属性
        if (div.hasAttribute('width')) {
          const attrWidth = parseInt(div.getAttribute('width'));
          if (attrWidth < 50 || attrWidth > 800) {
            div.style.width = 'auto';
            div.style.maxWidth = '100%';
            div.removeAttribute('width');
          }
        }
      });

      // 处理图片
      const images = contentContainer.querySelectorAll('img');
      images.forEach(img => {
        // 确保图片不超出容器
        img.style.maxWidth = '100%';
        img.style.height = 'auto';

        // 移除可能导致问题的属性
        if (img.hasAttribute('width') && parseInt(img.getAttribute('width')) > 600) {
          img.removeAttribute('width');
        }
      });

      // 处理链接
      const links = contentContainer.querySelectorAll('a');
      links.forEach(link => {
        // 确保链接在新窗口打开
        link.setAttribute('target', '_blank');
        link.setAttribute('rel', 'noopener noreferrer');
      });

      // 自动识别纯文本中的URL并转换为可点击链接
      if (contentContainer.querySelector('.plain-content')) {
        const plainContent = contentContainer.querySelector('.plain-content');
        const text = plainContent.textContent;
        const urlRegex = /(https?:\/\/[^\s]+)/g;
        if (urlRegex.test(text)) {
          plainContent.innerHTML = text.replace(urlRegex, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
        }
      }

      // 处理垂直文本的特殊情况 - 针对微软邮件中的验证码等内容
      if (isMicrosoft) {
        // 查找可能包含验证码的元素
        const possibleCodeElements = contentContainer.querySelectorAll('div, p, span, td');
        possibleCodeElements.forEach(element => {
          const text = element.textContent.trim();
          // 检查是否可能是验证码（纯数字，长度4-8位）
          if (/^\d{4,8}$/.test(text)) {
            element.style.fontSize = '18px';
            element.style.fontWeight = '600';
            element.style.color = '#333333';
            element.style.margin = '16px 0';
            element.style.padding = '8px 0';
            element.style.textAlign = 'center';
            element.style.letterSpacing = '2px';
          }
        });
      }

    } catch (error) {
      console.error('修复垂直文本失败:', error);
    }
  }, 500);
}

// 检查是否是纯文本内容
const isPlainText = computed(() => {
  if (!props.mail || !props.mail.content) return true // 默认当作纯文本处理

  // 兼容新旧格式
  if (typeof props.mail.content === 'object') {
    return props.mail.content.content_type === 'text/plain' ||
           !props.mail.content.has_html
  }

  // 如果不是HTML，则认为是纯文本
  return !isHtmlContent.value
})

// 检查是否是GitHub邮件
const isGitHubEmail = computed(() => {
  if (!props.mail) return false

  // 检查发件人
  if (props.mail.sender &&
      (props.mail.sender.includes('github.com') ||
       props.mail.sender.includes('GitHub') ||
       props.mail.sender.includes('edu-noreply@github.com'))) {
    return true
  }

  // 检查主题
  if (props.mail.subject &&
      (props.mail.subject.includes('GitHub') ||
       props.mail.subject.includes('[GitHub'))) {
    return true
  }

  // 检查内容
  if (mailContent.value) {
    const content = mailContent.value.toLowerCase()
    if (content.includes('github.com') ||
        content.includes('github education') ||
        content.includes('@github') ||
        content.includes('github billing')) {
      return true
    }
  }

  return false
})

// 检查是否是Microsoft邮件
const isMicrosoftEmail = computed(() => {
  if (!props.mail) return false

  // 检查发件人 - 更严格的匹配条件
  if (props.mail.sender) {
    const senderLower = props.mail.sender.toLowerCase()
    if (senderLower.includes('@microsoft.com') ||
        senderLower.includes('@outlook.com') ||
        senderLower.includes('@office365.com') ||
        senderLower.includes('@live.com') ||
        senderLower.includes('@hotmail.com') ||
        senderLower.includes('@msn.com') ||
        // 仅当发件人是学校邮箱且主题包含验证相关内容时才识别为微软邮件
        (senderLower.includes('@stu.neu.edu.cn') &&
         props.mail.subject &&
         (props.mail.subject.includes('验证') ||
          props.mail.subject.includes('账户') ||
          props.mail.subject.includes('帐户') ||
          props.mail.subject.includes('Microsoft')))) {
      return true
    }
  }

  // 检查主题 - 更严格的匹配条件
  if (props.mail.subject) {
    const subjectLower = props.mail.subject.toLowerCase()
    // 主题必须明确包含Microsoft相关关键词
    if (subjectLower.includes('microsoft') ||
        subjectLower.includes('outlook') ||
        subjectLower.includes('office 365') ||
        // 或者是验证邮件且内容中包含微软相关标识
        ((subjectLower.includes('验证') ||
          subjectLower.includes('账户') ||
          subjectLower.includes('帐户')) &&
         mailContent.value &&
         (mailContent.value.toLowerCase().includes('microsoft') ||
          mailContent.value.toLowerCase().includes('outlook')))) {
      return true
    }
  }

  // 检查内容 - 更严格的匹配条件
  if (mailContent.value) {
    const content = mailContent.value.toLowerCase()
    // 必须包含明确的微软邮件特征
    if ((content.includes('class="msonormal"') || content.includes('style="mso-')) ||
        // 或者同时包含微软域名和明确的微软标识
        ((content.includes('@microsoft.com') ||
          content.includes('@outlook.com') ||
          content.includes('@office365.com')) &&
         (content.includes('microsoft corporation') ||
          content.includes('验证你的电子邮件地址') &&
          content.includes('microsoft')))) {
      return true
    }
  }

  return false
})

// 检查是否是Notion邮件
const isNotionEmail = computed(() => {
  if (!props.mail) return false

  // 检查发件人
  if (props.mail.sender &&
      (props.mail.sender.includes('notion.so') ||
       props.mail.sender.includes('Notion'))) {
    return true
  }

  // 检查主题
  if (props.mail.subject &&
      props.mail.subject.includes('Notion')) {
    return true
  }

  // 检查内容
  if (mailContent.value) {
    const content = mailContent.value.toLowerCase()
    if (content.includes('notion.so') ||
        content.includes('data-block-id') ||
        content.includes('notion-')) {
      return true
    }
  }

  return false
})

const sanitizedContent = computed(() => {
  // 使用DOMPurify清理HTML内容，允许安全的标签和属性
  const cleanHtml = DOMPurify.sanitize(mailContent.value, {
    ALLOWED_TAGS: [
      'a', 'abbr', 'article', 'b', 'blockquote', 'br', 'caption', 'code', 'div',
      'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'li', 'nl', 'ol',
      'p', 'pre', 'span', 'strike', 'strong', 'table', 'tbody', 'td', 'th', 'thead',
      'tr', 'u', 'ul', 'font', 'center', 'style', 'head', 'body', 'html', 'meta',
      'title', 'link',
      'section', 'header', 'footer', 'nav', 'main', 'aside', 'figure', 'figcaption',
      'address', 'cite', 'dd', 'dl', 'dt', 'mark', 's', 'small', 'sub', 'sup', 'time',
      'wbr', 'col', 'colgroup', 'source', 'track', 'video', 'audio', 'canvas', 'map',
      'area', 'fieldset', 'legend', 'label', 'datalist', 'optgroup', 'output', 'progress'
    ],
    ALLOWED_ATTR: [
      'href', 'src', 'alt', 'title', 'style', 'class', 'target', 'id', 'width', 'height',
      'align', 'valign', 'bgcolor', 'border', 'cellpadding', 'cellspacing', 'colspan',
      'rowspan', 'scope', 'summary', 'headers', 'abbr', 'axis', 'charset', 'content',
      'http-equiv', 'name', 'scheme', 'rev', 'rel', 'type', 'xmlns', 'lang', 'dir',
      'face', 'color', 'background', 'marginwidth', 'marginheight', 'hspace', 'vspace',
      'noshade', 'nowrap', 'size', 'start', 'value', 'frameborder', 'scrolling', 'shape',
      'data-*', 'aria-*', 'role', 'tabindex', 'disabled', 'checked', 'selected', 'readonly',
      'placeholder', 'autocomplete', 'autofocus', 'required', 'multiple', 'min', 'max',
      'step', 'pattern', 'accept', 'capture', 'for', 'form', 'list', 'max', 'maxlength',
      'minlength', 'spellcheck', 'translate', 'wrap'
    ],
    // 禁止表单提交相关危险属性，降低钓鱼 HTML 风险
    FORBID_ATTR: ['formaction', 'formenctype', 'formmethod', 'formnovalidate', 'formtarget'],
    ALLOW_DATA_ATTR: true,
    ADD_ATTR: ['target'],
    WHOLE_DOCUMENT: isGitHubEmail.value || isMicrosoftEmail.value || isNotionEmail.value, // 对特殊邮件保留完整文档结构
    SANITIZE_DOM: true,
    KEEP_CONTENT: true
  });
  let html = cleanHtml
  if (!isGitHubEmail.value && !isMicrosoftEmail.value && !isNotionEmail.value) {
    html = cleanHtml.replace(/<img\s/gi, '<img loading="eager" ')
  }
  const bootstrap = `
    <style>
      html, body { margin:0; padding:0; overflow-x:hidden !important; }
      body, .root, .main { width:100% !important; max-width:100% !important; }
      table, td, th, center, .container, .wrapper, .content { width:100% !important; max-width:100% !important; }
      img { max-width:100% !important; height:auto !important; }
    </style>
    <script>(function(){
      function apply(){
        try {
          var selectors = [
            'table[width]', 'table[style*="width"]',
            'td[width]', 'th[width]', 'td[style*="width"]', 'th[style*="width"]',
            'div[width]', 'div[style*="width"]',
            'center > table',
            '[style*="max-width"]', '[style*="min-width"]'
          ];
          var els = document.querySelectorAll(selectors.join(','));
          els.forEach(function(el){
            el.style.width = '100%';
            el.style.maxWidth = '100%';
            if (el.hasAttribute('width')) el.removeAttribute('width');
            if (el.style && el.style.minWidth && parseInt(el.style.minWidth) < 200) el.style.minWidth = '200px';
            if (el.style && el.style.marginLeft) el.style.marginLeft = '0';
            if (el.style && el.style.marginRight) el.style.marginRight = '0';
          });
          var h = Math.max(
            document.body.scrollHeight,
            document.documentElement.scrollHeight,
            document.body.offsetHeight,
            document.documentElement.offsetHeight
          );
          parent.postMessage({ type:'email-frame-resize', height: h }, '*');
        } catch(e) {}
      }
      document.addEventListener('DOMContentLoaded', function(){ apply(); setTimeout(apply, 500); setTimeout(apply, 1500); setTimeout(apply, 3000); });
    })();<\/script>
  `
  return html + bootstrap;
})

const contentFrame = ref(null)

const updateFrameHeight = () => {
  const f = contentFrame.value
  if (f && f.contentWindow && f.contentWindow.document) {
    const doc = f.contentWindow.document
    const h = Math.max(
      doc.body.scrollHeight,
      doc.documentElement.scrollHeight,
      doc.body.offsetHeight,
      doc.documentElement.offsetHeight
    )
    const viewport = Math.max(window.innerHeight || 0, 700)
    f.style.height = `${Math.max(h, viewport * 0.9)}px`
  }
}

const onFrameLoad = () => {
  updateFrameHeight()
  setTimeout(updateFrameHeight, 500)
  setTimeout(updateFrameHeight, 1500)
  setTimeout(updateFrameHeight, 3000)
}

const hasAttachments = computed(() => {
  return props.mail && props.mail.has_attachments && props.attachments && props.attachments.length > 0
})

const attachmentsCount = computed(() => {
  return props.attachments ? props.attachments.length : 0
})

const senderInitial = computed(() => {
  if (!props.mail || !props.mail.sender) return ''

  // 提取发件人的第一个字符作为头像
  const sender = props.mail.sender.trim()
  if (sender.length > 0) {
    // 尝试提取名字部分
    const match = sender.match(/^"?([^"<]+)"?\s*(?:<.*>)?$/)
    if (match && match[1]) {
      return match[1].trim()[0].toUpperCase()
    }
    return sender[0].toUpperCase()
  }
  return ''
})

// 方法
const formatDate = (date) => {
  if (!date) return ''

  const dateObj = dayjs(date)
  const now = dayjs()

  // 如果是今天的邮件，只显示时间
  if (dateObj.isSame(now, 'day')) {
    return dateObj.format('HH:mm')
  }

  // 如果是昨天的邮件，显示"昨天"和时间
  if (dateObj.isSame(now.subtract(1, 'day'), 'day')) {
    return `昨天 ${dateObj.format('HH:mm')}`
  }

  // 如果是今年的邮件，不显示年份
  if (dateObj.isSame(now, 'year')) {
    return dateObj.format('MM-DD HH:mm')
  }

  // 其他情况显示完整日期
  return dateObj.format('YYYY-MM-DD HH:mm')
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B'

  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 专门处理微软邮件的样式问题
const fixMicrosoftEmailStyles = (html) => {
  if (!html) return '';

  try {
    // 创建一个临时的DOM元素来处理HTML
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;

    // 检查是否包含JSON格式的内容
    if (html.includes('["content":')) {
      try {
        // 尝试提取JSON内容
        const jsonMatch = html.match(/\["content":\s*"(.+?)"\]/s);
        if (jsonMatch && jsonMatch[1]) {
          let content = jsonMatch[1];
          // 解码转义的JSON字符串
          content = content
            .replace(/\\"/g, '"')
            .replace(/\\n/g, '\n')
            .replace(/\\r/g, '')
            .replace(/\\t/g, '\t')
            .replace(/\\\\/g, '\\');

          tempDiv.innerHTML = content;
        }
      } catch (jsonError) {
        console.error('解析邮件JSON内容失败:', jsonError);
      }
    }

    // 移除顶部的Microsoft标题栏（如果存在）
    const msHeader = tempDiv.querySelector('[class*="header"], [class*="Header"], [class*="banner"], [class*="Banner"]');
    if (msHeader && msHeader.innerHTML.toLowerCase().includes('microsoft')) {
      msHeader.remove();
    }

    // 移除左侧的灰色空白区域（通常是导航栏或装饰元素）
    const leftSidebars = tempDiv.querySelectorAll('td[style*="background-color:#e3e3e3"], td[style*="background-color: #e3e3e3"], td[bgcolor="#e3e3e3"], td[style*="background:#e3e3e3"], td[width="1"], td[width="2"], td[width="3"], td[width="4"], td[width="5"]');
    leftSidebars.forEach(sidebar => {
      if (sidebar.offsetWidth < 50 || (sidebar.getAttribute('width') && parseInt(sidebar.getAttribute('width')) < 50)) {
        sidebar.remove();
      }
    });

    // 处理Microsoft特有的表格样式
    const tables = tempDiv.querySelectorAll('table');
    tables.forEach(table => {
      // 移除表格边框，使用更简洁的样式
      table.style.borderCollapse = 'collapse';
      table.style.width = '100%';
      table.style.maxWidth = '100%';
      table.style.margin = '16px auto';
      table.style.tableLayout = 'auto';

      // 如果表格有border属性，设置为0
      if (table.hasAttribute('border')) {
        table.setAttribute('border', '0');
      }

      // 移除可能导致问题的属性
      ['width', 'height', 'cellspacing', 'cellpadding', 'align', 'bgcolor'].forEach(attr => {
        if (table.hasAttribute(attr)) {
          table.removeAttribute(attr);
        }
      });

      // 处理表格单元格
      const cells = table.querySelectorAll('td, th');
      cells.forEach(cell => {
        // 改进单元格样式
        cell.style.border = 'none';
        cell.style.borderBottom = '1px solid #f0f0f0';
        cell.style.padding = '10px 16px';
        cell.style.whiteSpace = 'normal';
        cell.style.wordBreak = 'break-word';
        cell.style.wordWrap = 'break-word';
        cell.style.textAlign = 'left';
        cell.style.verticalAlign = 'top';

        // 修复垂直排列的文本
        if (cell.textContent && cell.textContent.trim().length > 0) {
          cell.style.minWidth = '100px';
          cell.style.width = 'auto';
        }
      });

      // 处理表格行
      const rows = table.querySelectorAll('tr');
      rows.forEach(row => {
        row.style.height = 'auto';
      });
    });

    // 处理Microsoft特有的div元素
    const divs = tempDiv.querySelectorAll('div');
    divs.forEach(div => {
      // 处理Microsoft特有的类
      if (div.className && (
          div.className.includes('MsoNormal') ||
          div.className.includes('outlook') ||
          div.className.includes('microsoft') ||
          div.className.includes('x_'))) {
        div.style.width = 'auto';
        div.style.maxWidth = '100%';
        div.style.wordWrap = 'break-word';
        div.style.wordBreak = 'break-word';
        div.style.margin = '10px 0';
        div.style.lineHeight = '1.6';
        div.style.textAlign = 'left';
      }

      // 检查是否是窄列布局
      if (div.offsetWidth < 50 ||
          (div.style.width && parseInt(div.style.width) < 50) ||
          (div.hasAttribute('width') && parseInt(div.getAttribute('width')) < 50)) {
        div.style.width = 'auto';
        div.style.minWidth = '200px';
        div.style.maxWidth = '100%';
      }

      // 特殊处理验证码邮件中的内容容器
      if (div.textContent && div.textContent.trim().match(/^\d{4,8}$/)) {
        div.style.fontSize = '24px';
        div.style.fontWeight = '600';
        div.style.color = '#333333';
        div.style.margin = '24px 0';
        div.style.padding = '12px 0';
        div.style.textAlign = 'center';
        div.style.letterSpacing = '4px';
        div.style.display = 'block';
      }
    });

    // 处理Microsoft特有的段落元素
    const paragraphs = tempDiv.querySelectorAll('p');
    paragraphs.forEach(p => {
      if (p.className && (
          p.className.includes('MsoNormal') ||
          p.className.includes('outlook') ||
          p.className.includes('microsoft'))) {
        p.style.margin = '10px 0';
        p.style.lineHeight = '1.6';
        p.style.wordWrap = 'break-word';
        p.style.wordBreak = 'break-word';
      }

      // 检查段落是否包含验证码
      if (p.textContent && p.textContent.trim().match(/^\d{4,8}$/)) {
        p.style.fontSize = '24px';
        p.style.fontWeight = '600';
        p.style.color = '#333333';
        p.style.margin = '24px 0';
        p.style.padding = '12px 0';
        p.style.textAlign = 'center';
        p.style.letterSpacing = '4px';
      }
    });

    // 处理链接
    const links = tempDiv.querySelectorAll('a');
    links.forEach(link => {
      // 确保链接在新窗口打开
      link.setAttribute('target', '_blank');
      link.setAttribute('rel', 'noopener noreferrer');

      // 设置链接颜色为微软蓝
      link.style.color = '#0078d4';
    });

    // 处理图片
    const images = tempDiv.querySelectorAll('img');
    images.forEach(img => {
      // 确保图片不超出容器
      img.style.maxWidth = '100%';
      img.style.height = 'auto';

      // 移除Microsoft Logo图片
      const src = img.getAttribute('src') || '';
      const alt = img.getAttribute('alt') || '';
      if ((src.toLowerCase().includes('microsoft') || alt.toLowerCase().includes('microsoft')) &&
          img.width < 200 && img.height < 100) {
        img.style.display = 'none';
      }
    });

    // 处理span元素，特别是验证码
    const spans = tempDiv.querySelectorAll('span');
    spans.forEach(span => {
      // 检查span是否包含验证码
      if (span.textContent && span.textContent.trim().match(/^\d{4,8}$/)) {
        span.style.fontSize = '24px';
        span.style.fontWeight = '600';
        span.style.color = '#333333';
        span.style.display = 'block';
        span.style.margin = '24px 0';
        span.style.padding = '12px 0';
        span.style.textAlign = 'center';
        span.style.letterSpacing = '4px';
      }
    });

    return tempDiv.innerHTML;
  } catch (error) {
    console.error('修复微软邮件样式失败:', error);
    return html;
  }
};

// 修复GitHub邮件样式和其他特殊格式邮件
const fixGitHubEmailStyles = (html) => {
  if (!html) return '';

  try {
    // 创建一个临时的DOM元素来处理HTML
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;

    // 检查是否包含JSON格式的内容
    if (html.includes('["content":')) {
      try {
        // 尝试提取JSON内容
        const jsonMatch = html.match(/\["content":\s*"(.+?)"\]/s);
        if (jsonMatch && jsonMatch[1]) {
          let content = jsonMatch[1];
          // 解码转义的JSON字符串
          content = content
            .replace(/\\"/g, '"')
            .replace(/\\n/g, '\n')
            .replace(/\\r/g, '')
            .replace(/\\t/g, '\t')
            .replace(/\\\\/g, '\\');

          tempDiv.innerHTML = content;
        }
      } catch (jsonError) {
        console.error('解析邮件JSON内容失败:', jsonError);
      }
    }

    // 修复表格样式
    const tables = tempDiv.querySelectorAll('table');
    tables.forEach(table => {
      // 移除表格边框，使用更简洁的样式
      table.style.borderCollapse = 'collapse';
      table.style.width = '100%';
      table.style.maxWidth = '100%';
      table.style.margin = '16px auto'; // 居中显示
      table.style.tableLayout = 'auto';

      // 如果表格有border属性，设置为0
      if (table.hasAttribute('border')) {
        table.setAttribute('border', '0');
      }

      // 处理表格单元格
      const cells = table.querySelectorAll('td, th');
      cells.forEach(cell => {
        // 移除单元格边框
        cell.style.border = 'none';
        cell.style.borderBottom = '1px solid #f0f0f0';
        cell.style.padding = '10px 16px';
        cell.style.whiteSpace = 'normal';
        cell.style.wordBreak = 'break-word';
        cell.style.wordWrap = 'break-word';
        cell.style.textAlign = 'left';

        // 修复垂直排列的文本
        if (cell.textContent && cell.textContent.trim().length > 0 &&
            (cell.offsetWidth < 30 || cell.getAttribute('width') < 30)) {
          cell.style.minWidth = '100px';
          cell.style.width = 'auto';
          if (cell.hasAttribute('width')) {
            cell.removeAttribute('width');
          }
        }
      });

      // 处理最后一行的单元格，移除底部边框
      const rows = table.querySelectorAll('tr');
      if (rows.length > 0) {
        const lastRow = rows[rows.length - 1];
        const lastRowCells = lastRow.querySelectorAll('td, th');
        lastRowCells.forEach(cell => {
          cell.style.borderBottom = 'none';
        });
      }
    });

    // 修复链接样式
    const links = tempDiv.querySelectorAll('a');
    links.forEach(link => {
      // 确保链接在新窗口打开
      link.setAttribute('target', '_blank');
      link.setAttribute('rel', 'noopener noreferrer');

      // 添加样式 - 根据邮件类型使用不同的颜色
      if (isGitHubEmail.value) {
        link.style.color = '#0366d6';
      } else {
        link.style.color = 'var(--primary-color)';
      }
    });

    // 修复图片样式
    const images = tempDiv.querySelectorAll('img');
    images.forEach(img => {
      // 确保图片不超出容器
      img.style.maxWidth = '100%';
      img.style.height = 'auto';
    });

    // 处理特殊字符和转义序列
    const textNodes = getTextNodes(tempDiv);
    textNodes.forEach(node => {
      if (node.nodeValue) {
        // 替换转义序列
        let text = node.nodeValue
          .replace(/\\n/g, '\n')
          .replace(/\\r/g, '')
          .replace(/\\t/g, '    ')
          .replace(/\\\\/g, '\\')
          .replace(/\\'/g, "'")
          .replace(/\\"/g, '"')
          .replace(/\n\n+/g, '\n\n'); // 合并多个连续换行

        // 处理UTF-8编码问题
        if (text.includes('Ã') || text.includes('Â')) {
          try {
            // 尝试修复UTF-8编码问题
            const decoder = new TextDecoder('utf-8')
            const encoder = new TextEncoder()
            const bytes = encoder.encode(text)
            text = decoder.decode(bytes)
          } catch (error) {
            console.error('处理文本编码失败:', error)
          }
        }

        node.nodeValue = text;
      }
    });

    // 修复垂直排列的文本问题
    const divs = tempDiv.querySelectorAll('div');
    divs.forEach(div => {
      // 检查是否是垂直排列的文本容器
      const text = div.textContent.trim();
      const children = div.children;

      // 如果文本内容较多但宽度很窄，可能是垂直排列的文本
      if (text.length > 10 && (div.offsetWidth < 50 || div.getAttribute('width') < 50) && children.length === 0) {
        div.style.width = 'auto';
        div.style.minWidth = '200px';
        div.style.whiteSpace = 'normal';
        div.style.wordBreak = 'break-word';
        div.style.wordWrap = 'break-word';
        div.style.textAlign = 'left';
        if (div.hasAttribute('width')) {
          div.removeAttribute('width');
        }
      }

      // 处理可能包含垂直文本的容器
      if (div.style.width === '0px' || div.style.width === '0' ||
          div.style.width === '1px' || div.style.width === '1') {
        div.style.width = 'auto';
        div.style.minWidth = '200px';
      }
    });

    // 支持更多邮件服务商的特殊样式
    // Gmail 特定样式
    const gmailElements = tempDiv.querySelectorAll('[class*="gmail"]');
    gmailElements.forEach(element => {
      element.style.maxWidth = '100%';
      if (element.hasAttribute('width')) {
        element.removeAttribute('width');
      }
    });

    // Outlook 特定样式
    const outlookElements = tempDiv.querySelectorAll('[class*="outlook"], [class*="office"], [class*="mso"]');
    outlookElements.forEach(element => {
      element.style.maxWidth = '100%';
      element.style.width = 'auto';
      if (element.hasAttribute('width')) {
        element.removeAttribute('width');
      }
    });

    return tempDiv.innerHTML;
  } catch (error) {
    console.error('修复邮件样式失败:', error);
    return html;
  }
}

// 获取所有文本节点
const getTextNodes = (element) => {
  const textNodes = [];
  const walker = document.createTreeWalker(
    element,
    NodeFilter.SHOW_TEXT,
    null,
    false
  );

  let node;
  while (node = walker.nextNode()) {
    textNodes.push(node);
  }

  return textNodes;
}

const sanitizeHtml = (html) => {
  if (!html) return ''
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'a', 'b', 'br', 'div', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'i', 'img', 'li', 'ol', 'p', 'span', 'strong', 'table', 'tbody',
      'td', 'th', 'thead', 'tr', 'u', 'ul', 'font', 'blockquote', 'hr',
      'pre', 'code', 'col', 'colgroup', 'section', 'header', 'footer',
      'nav', 'article', 'aside', 'figure', 'figcaption', 'address', 'main',
      'caption', 'center', 'cite', 'dd', 'dl', 'dt', 'mark', 's', 'small',
      'strike', 'sub', 'sup', 'style', 'head', 'body', 'html', 'meta'
    ],
    ALLOWED_ATTR: [
      'href', 'target', 'src', 'alt', 'style', 'class', 'id', 'width', 'height',
      'align', 'valign', 'bgcolor', 'border', 'cellpadding', 'cellspacing',
      'color', 'colspan', 'dir', 'face', 'frame', 'frameborder', 'headers',
      'hspace', 'lang', 'marginheight', 'marginwidth', 'nowrap', 'rel',
      'rev', 'rowspan', 'scrolling', 'shape', 'span', 'summary', 'title',
      'usemap', 'vspace', 'start', 'type', 'value', 'size', 'data-*',
      'charset', 'content', 'http-equiv', 'name'
    ],
    ALLOW_DATA_ATTR: true,
    ADD_ATTR: ['target'],
    WHOLE_DOCUMENT: false,
    SANITIZE_DOM: true,
    KEEP_CONTENT: true
  })
}

// 附件相关方法
const isImageAttachment = (attachment) => {
  if (!attachment || !attachment.content_type) return false
  return attachment.content_type.startsWith('image/')
}

const isPdfAttachment = (attachment) => {
  if (!attachment || !attachment.content_type) return false
  return attachment.content_type === 'application/pdf'
}

const isTextAttachment = (attachment) => {
  if (!attachment || !attachment.content_type) return false
  return attachment.content_type.startsWith('text/') ||
         attachment.filename.endsWith('.txt') ||
         attachment.filename.endsWith('.log') ||
         attachment.filename.endsWith('.md') ||
         attachment.filename.endsWith('.json') ||
         attachment.filename.endsWith('.csv')
}

const isArchiveAttachment = (attachment) => {
  if (!attachment || !attachment.filename) return false
  const filename = attachment.filename.toLowerCase()
  return filename.endsWith('.zip') ||
         filename.endsWith('.rar') ||
         filename.endsWith('.7z') ||
         filename.endsWith('.tar') ||
         filename.endsWith('.gz')
}

const canPreviewAttachment = (attachment) => {
  return isImageAttachment(attachment) ||
         isPdfAttachment(attachment) ||
         isTextAttachment(attachment)
}

const downloadAttachment = (attachmentId, filename) => {
  const token = localStorage.getItem('token')
  const downloadUrl = `/api/attachments/${attachmentId}/download`

  // 创建一个隐藏的a标签用于下载
  const link = document.createElement('a')
  link.href = downloadUrl
  link.setAttribute('download', filename)
  link.setAttribute('target', '_blank')

  // 添加认证头
  fetch(downloadUrl, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })
  .then(response => response.blob())
  .then(blob => {
    const url = window.URL.createObjectURL(blob)
    link.href = url
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  })
  .catch(error => {
    console.error('下载附件失败:', error)
    ElMessage.error('下载附件失败')
  })
}

const previewAttachment = (attachment) => {
  previewingAttachment.value = attachment
  previewDialogVisible.value = true

  if (isImageAttachment(attachment) || isPdfAttachment(attachment)) {
    const token = localStorage.getItem('token')
    const downloadUrl = `/api/attachments/${attachment.id}/download`

    fetch(downloadUrl, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    .then(response => response.blob())
    .then(blob => {
      previewUrl.value = URL.createObjectURL(blob)
    })
    .catch(error => {
      console.error('获取附件预览失败:', error)
      ElMessage.error('获取附件预览失败')
    })
  } else if (isTextAttachment(attachment)) {
    const token = localStorage.getItem('token')
    const downloadUrl = `/api/attachments/${attachment.id}/download`

    fetch(downloadUrl, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    .then(response => response.text())
    .then(text => {
      previewContent.value = text
    })
    .catch(error => {
      console.error('获取附件预览失败:', error)
      ElMessage.error('获取附件预览失败')
    })
  }
}

// 下载原始邮件
const downloadOriginalEmail = () => {
  if (!props.mail || !props.mail.id) {
    ElMessage.error('无法下载邮件，邮件ID不存在')
    return
  }

  const token = localStorage.getItem('token')
  const downloadUrl = `/api/mails/${props.mail.id}/download`

  // 创建一个隐藏的a标签用于下载
  const link = document.createElement('a')
  link.href = downloadUrl
  link.setAttribute('download', `email_${props.mail.id}.eml`)
  link.setAttribute('target', '_blank')

  // 添加认证头
  fetch(downloadUrl, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`)
    }
    return response.blob()
  })
  .then(blob => {
    const url = window.URL.createObjectURL(blob)
    link.href = url
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('邮件下载成功')
  })
  .catch(error => {
    console.error('下载邮件失败:', error)
    ElMessage.error('下载邮件失败，可能后端未实现此功能')
  })
}

// 监听邮件内容变化，修复垂直排列的文本
onMounted(() => {
  // 初始加载时修复垂直文本
  fixVerticalText()
  setTimeout(updateFrameHeight, 300)
  window.addEventListener('message', (e) => {
    if (e && e.data && e.data.type === 'email-frame-resize' && contentFrame.value) {
      const target = contentFrame.value
      const newHeight = Math.max(e.data.height || 0, Math.floor((window.innerHeight || 800) * 0.9))
      target.style.height = newHeight + 'px'
    }
  })
})

// 监听邮件内容变化
watch(() => props.mail, () => {
  // 邮件内容变化时重新修复垂直文本
  fixVerticalText()
  setTimeout(updateFrameHeight, 300)
}, { deep: true })
</script>

<style scoped>
.html-frame {
  width: 100%;
  border: 0;
  background: transparent;
  display: block;
}

.default-container {
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  box-sizing: border-box;
  overflow: hidden;
}

.default-email {
  background-color: #ffffff;
}
.email-content-viewer {
  display: flex;
  flex-direction: column;
  width: 100%;
  background-color: #fff;
  padding: 0 0 20px 0;
  max-width: 100%;
  margin: 0 auto;
}

.email-header {
  padding: 20px 24px 16px;
  background-color: #fff;
  border-bottom: 1px solid #f0f0f0;
  margin-bottom: 16px;
}

.header-item {
  display: flex;
  margin-bottom: 8px;
}

.subject h2 {
  margin: 0 0 20px 0;
  font-size: 1.5rem;
  color: #303133;
  word-break: break-word;
  font-weight: 500;
  line-height: 1.3;
}

.header-details {
  display: flex;
  flex-direction: column;
  gap: 10px;
  color: #606266;
}

.label {
  width: 70px;
  color: #909399;
  font-weight: 400;
}

.value {
  flex: 1;
  color: #303133;
  word-break: break-word;
}

.sender {
  display: flex;
  align-items: center;
  gap: 10px;
}

.sender-avatar {
  background-color: var(--primary-color);
  color: white;
  font-weight: bold;
}

.email-attachments {
  padding: 16px 24px;
  background-color: #fafafa;
  margin: 0 24px 16px;
  border-radius: 4px;
  border-left: 3px solid #dcdfe6;
}

.attachments-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-weight: 500;
  color: #303133;
}

.attachments-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.attachment-item {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  background-color: #fff;
  border-radius: 4px;
  width: calc(50% - 6px);
  transition: all 0.2s ease;
  border: 1px solid #f0f0f0;
}

.attachment-icon {
  margin-right: 16px;
  font-size: 24px;
  color: #606266;
}

.attachment-info {
  flex: 1;
  min-width: 0;
}

.attachment-name {
  font-weight: 500;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.attachment-size {
  font-size: 12px;
  color: #909399;
}

.attachment-actions {
  display: flex;
  gap: 8px;
}

.attachment-item:hover {
  background-color: #f5f7fa;
}

.email-content {
  padding: 0 24px;
  overflow: auto;
  width: 100%;
  max-width: 100%;
  margin: 0 auto;
  background-color: #ffffff;
  box-sizing: border-box;
}

.html-content {
  width: 100%;
  max-width: 100%;
  overflow-x: visible; /* 修改为visible，避免不必要的滚动条 */
  line-height: 1.6;
  word-break: break-word;
  word-wrap: break-word;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  color: #333333;
  font-size: 15px;
  padding: 0;
  box-sizing: border-box;
}

/* 基本元素样式 */
.html-content :deep(img) {
  max-width: 100%;
  height: auto;
  display: block;
  margin: 16px auto;
  border-radius: 4px;
  object-fit: contain;
}

.html-content :deep(a) {
  color: var(--primary-color);
  text-decoration: none;
  word-break: break-all;
  transition: all 0.2s ease;
}

.html-content :deep(a:hover) {
  text-decoration: underline;
}

/* 表格样式优化 - 更简洁的表格样式 */
.html-content :deep(table) {
  max-width: 100%;
}

/* 使表格在小屏幕上可滚动，但在大屏幕上正常显示 */
@media (max-width: 767px) {
  .html-content :deep(table) {
    display: block;
    overflow-x: auto;
    white-space: nowrap;
  }
}

/* 在大屏幕上强制表格正常显示 */
@media (min-width: 768px) {
  .html-content :deep(table) {
    display: table;
    white-space: normal;
    table-layout: auto;
  }

  /* 强制表格单元格自动换行 */
  .html-content :deep(td), .html-content :deep(th) {
    white-space: normal !important;
    word-break: break-word !important;
  }
}

.html-content :deep(th) {
  white-space: normal;
  word-break: break-word;
}

.html-content :deep(td) {
  white-space: normal;
  word-break: break-word;
}

.html-content :deep(tr:nth-child(even)) {
  background-color: #fafafa;
}

.html-content :deep(tr:last-child) td {
  border-bottom: none;
}

.html-content :deep(blockquote) {
  border-left: 3px solid #dcdfe6;
  padding: 12px 16px;
  margin: 16px 0;
  background-color: #fafafa;
  color: #606266;
  border-radius: 0;
  font-style: italic;
}

.html-content :deep(pre) {
  background-color: #f8f9fa;
  padding: 16px;
  border-radius: 2px;
  overflow-x: auto;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 14px;
  line-height: 1.5;
  margin: 16px 0;
  border: 1px solid #f0f0f0;
}

.html-content :deep(p) {
  margin: 12px 0;
  line-height: 1.7;
}

.html-content :deep(h1), .html-content :deep(h2), .html-content :deep(h3),
.html-content :deep(h4), .html-content :deep(h5), .html-content :deep(h6) {
  margin-top: 24px;
  margin-bottom: 16px;
  font-weight: 600;
  line-height: 1.25;
  color: #303133;
}

.html-content :deep(ul), .html-content :deep(ol) {
  padding-left: 24px;
  margin: 16px 0;
}

/* GitHub邮件特定样式 */
.github-email {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  color: #24292e;
  line-height: 1.5;
  word-wrap: break-word;
  max-width: 900px;
  margin: 0 auto;
  padding: 0;
}

.html-content :deep(.panel) {
  background: #ffffff;
  border-radius: 4px;
  border: 1px solid #f0f0f0;
  padding: 20px;
  margin: 20px auto;
  max-width: 900px;
}

.html-content :deep(.email-heading) {
  color: #24292e;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  font-weight: 600;
  line-height: 1.3;
  font-size: 24px;
  margin: 16px 0;
  text-align: center;
}

.html-content :deep(.margin-bottom) {
  margin-bottom: 16px;
}

.html-content :deep(.container) {
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  padding: 0;
}

.html-content :deep(.footer-text) {
  font-size: 12px;
  color: #6a737d;
  text-align: center;
  margin-top: 32px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

/* 修复GitHub邮件中的emoji显示 */
.html-content :deep(span[style*="emoji"]) {
  display: inline-block;
  vertical-align: middle;
  font-size: 18px;
}

/* 修复GitHub邮件中的按钮样式 */
.html-content :deep(.btn), .html-content :deep(.button) {
  display: inline-block;
  padding: 8px 16px;
  margin: 16px 0;
  font-size: 14px;
  font-weight: 500;
  line-height: 1.5;
  text-align: center;
  white-space: nowrap;
  vertical-align: middle;
  cursor: pointer;
  background-color: #2ea44f;
  color: #ffffff !important;
  border-radius: 4px;
  text-decoration: none !important;
  border: none;
  transition: all 0.2s ease;
}

.html-content :deep(.btn:hover), .html-content :deep(.button:hover) {
  background-color: #2c974b;
  text-decoration: none !important;
}

/* GitHub特有的卡片样式 */
.html-content :deep(.Box), .html-content :deep(.card) {
  background-color: #ffffff;
  border-radius: 4px;
  margin: 16px 0;
  border: 1px solid #f0f0f0;
  overflow: hidden;
}

/* 支持更多邮件服务商的样式 */
/* Gmail 特定样式 */
.html-content :deep([class*="gmail"]) {
  max-width: 100% !important;
  width: auto !important;
  border: none !important;
  box-shadow: none !important;
}

/* Outlook/Microsoft 特定样式 */
.html-content :deep([class*="outlook"]),
.html-content :deep([class*="office"]),
.html-content :deep([class*="mso"]),
.html-content :deep([class*="microsoft"]) {
  max-width: 100% !important;
  width: auto !important;
  table-layout: auto !important;
  border: none !important;
  box-shadow: none !important;
}

/* Notion 特定样式 */
.html-content :deep([class*="notion"]) {
  max-width: 100% !important;
  width: auto !important;
  border: none !important;
  box-shadow: none !important;
}

/* 修复垂直排列的文本 */
.html-content :deep([width="0"]),
.html-content :deep([width="1"]),
.html-content :deep([width="2"]),
.html-content :deep([width="3"]),
.html-content :deep([width="4"]),
.html-content :deep([width="5"]),
.html-content :deep([style*="width:0"]),
.html-content :deep([style*="width:1"]),
.html-content :deep([style*="width:2"]),
.html-content :deep([style*="width:3"]),
.html-content :deep([style*="width:4"]),
.html-content :deep([style*="width:5"]) {
  width: auto !important;
  min-width: 100px !important;
}

/* 修复固定宽度的表格和容器 */
.html-content :deep([width]),
.html-content :deep([style*="width:"]) {
  max-width: 100% !important;
}

/* 修复Microsoft邮件特有的问题 */
.html-content :deep([class*="x_"]) {
  max-width: 100% !important;
  width: auto !important;
  border: none !important;
  box-shadow: none !important;
}

/* 修复Notion邮件特有的问题 */
.html-content :deep([data-block-id]) {
  max-width: 100% !important;
  width: auto !important;
  border: none !important;
  box-shadow: none !important;
}

.plain-content {
  white-space: pre-wrap;
  word-break: break-word;
  word-wrap: break-word;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  line-height: 1.6;
  margin: 0;
  padding: 16px 0;
  color: #333;
  font-size: 15px;
  width: 100%;
  max-width: 900px;
  overflow-x: auto;
  box-sizing: border-box;
  text-align: left;
  direction: ltr;
  background-color: #fff;
}

/* 自动识别并格式化纯文本中的链接 */
.plain-content a {
  color: var(--primary-color);
  text-decoration: none;
  transition: all 0.2s ease;
}

.plain-content a:hover {
  text-decoration: underline;
}

.attachment-preview {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 200px;
  width: 100%;
}

.image-preview img {
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
  border-radius: 4px;
}

.text-preview {
  width: 100%;
  max-height: 70vh;
  overflow: auto;
  background-color: #f8f9fa;
  padding: 16px;
  border-radius: 4px;
  border: 1px solid #f0f0f0;
}

.text-preview pre {
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 14px;
  line-height: 1.5;
}

.unsupported-preview {
  text-align: center;
  padding: 32px;
  background-color: #fafafa;
  border-radius: 4px;
  border: 1px solid #f0f0f0;
}

/* GitHub邮件特定样式 */
.github-container {
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  box-sizing: border-box;
  overflow: hidden;
}

.github-header {
  background-color: #2c974b;
  color: white;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  box-sizing: border-box;
  margin-bottom: 1px;
}

.github-logo {
  height: 24px;
  width: 24px;
  flex-shrink: 0;
  margin-right: 8px;
}

.github-title {
  font-size: 18px;
  font-weight: 600;
  color: white;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.github-email {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  color: #24292e;
  line-height: 1.5;
  word-wrap: break-word;
  background-color: white;
  padding: 20px;
  width: 100%;
  box-sizing: border-box;
}

/* Microsoft邮件特定样式 - 旧版本 */
.microsoft-container {
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  box-sizing: border-box;
  overflow: hidden;
  background-color: #ffffff;
}

.microsoft-header {
  background-color: #0078d4;
  color: white;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  box-sizing: border-box;
  margin-bottom: 1px;
}

.microsoft-logo {
  height: 24px;
  width: 24px;
  flex-shrink: 0;
  margin-right: 8px;
}

.microsoft-title {
  font-size: 18px;
  font-weight: 600;
  color: white;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.microsoft-email {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  color: #333333;
  line-height: 1.6;
  word-wrap: break-word;
  word-break: break-word;
  background-color: white;
  padding: 20px;
  width: 100%;
  box-sizing: border-box;
  text-align: left;
  display: block;
}

/* Microsoft邮件特定样式 - 新版本（优化后） */
.microsoft-container-new {
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  box-sizing: border-box;
  overflow: hidden;
  background-color: #ffffff;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.microsoft-email-new {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  color: #333333;
  line-height: 1.6;
  word-wrap: break-word;
  word-break: break-word;
  background-color: white;
  padding: 20px;
  width: 100%;
  box-sizing: border-box;
  text-align: left;
  display: block;
}

/* 微软邮件特定元素样式 - 旧版本 */
.microsoft-email :deep(p) {
  margin: 12px 0;
  line-height: 1.6;
}

.microsoft-email :deep(h1), .microsoft-email :deep(h2), .microsoft-email :deep(h3) {
  color: #333333;
  font-weight: 600;
  margin-top: 24px;
  margin-bottom: 16px;
  line-height: 1.3;
}

.microsoft-email :deep(a) {
  color: #0078d4;
  text-decoration: none;
}

.microsoft-email :deep(a:hover) {
  text-decoration: underline;
}

.microsoft-email :deep(table) {
  border-collapse: collapse;
  width: 100% !important;
  max-width: 100% !important;
  margin: 16px 0;
  border-radius: 4px;
  overflow: hidden;
  box-shadow: 0 1px 2px rgba(0,0,0,0.03);
  table-layout: auto !important;
  border: none !important;
}

.microsoft-email :deep(td), .microsoft-email :deep(th) {
  padding: 10px 16px;
  border: none;
  border-bottom: 1px solid #ebeef5;
  text-align: left;
  vertical-align: top;
  width: auto !important;
  min-width: 100px;
  white-space: normal !important;
  word-break: break-word !important;
  word-wrap: break-word !important;
}

.microsoft-email :deep(tr:last-child) td {
  border-bottom: none;
}

.microsoft-email :deep(th) {
  background-color: #f5f7fa;
  font-weight: 600;
}

.microsoft-email :deep(ul), .microsoft-email :deep(ol) {
  padding-left: 2em;
}

.microsoft-email :deep(li) {
  margin: 0.25em 0;
}

.microsoft-email :deep(code) {
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 85%;
  padding: 0.2em 0.4em;
  background-color: rgba(0, 0, 0, 0.05);
  border-radius: 3px;
}

.microsoft-email :deep(pre) {
  background-color: #f6f8fa;
  border-radius: 4px;
  font-size: 85%;
  line-height: 1.45;
  overflow: auto;
  padding: 16px;
  margin: 16px 0;
}

.microsoft-email :deep(img) {
  max-width: 100%;
  height: auto;
  display: block;
  margin: 16px auto;
  border-radius: 4px;
}

.microsoft-email :deep([class*="button"]), .microsoft-email :deep([role="button"]) {
  display: inline-block;
  padding: 8px 16px;
  margin: 16px 0;
  font-size: 14px;
  font-weight: 500;
  line-height: 1.5;
  text-align: center;
  white-space: nowrap;
  vertical-align: middle;
  cursor: pointer;
  background-color: #0078d4;
  color: #ffffff !important;
  border-radius: 4px;
  text-decoration: none !important;
  box-shadow: 0 1px 2px rgba(0,0,0,0.1);
}

.microsoft-email :deep([class*="button"]:hover), .microsoft-email :deep([role="button"]:hover) {
  background-color: #106ebe;
  text-decoration: none !important;
}

/* 修复Microsoft特有的样式问题 - 旧版本 */
.microsoft-email :deep([class*="MsoNormal"]),
.microsoft-email :deep([class*="outlook"]),
.microsoft-email :deep([class*="microsoft"]),
.microsoft-email :deep([class*="x_"]) {
  max-width: 100% !important;
  width: auto !important;
  word-wrap: break-word !important;
  word-break: break-word !important;
  margin: 10px 0 !important;
  line-height: 1.6 !important;
  text-align: left !important;
}

/* 修复验证码显示 - 旧版本 */
.microsoft-email :deep(.verification-code),
.microsoft-email :deep([class*="verification"]),
.microsoft-email :deep([class*="code"]) {
  font-size: 18px !important;
  font-weight: 600 !important;
  color: #333333 !important;
  margin: 16px 0 !important;
  padding: 8px 0 !important;
  text-align: center !important;
  letter-spacing: 2px !important;
}

/* 强制所有div使用正确的宽度 - 旧版本 */
.microsoft-email :deep(div) {
  max-width: 100% !important;
}

/* 修复微软邮件中的表格容器 - 旧版本 */
.microsoft-email :deep([class*="container"]),
.microsoft-email :deep([class*="wrapper"]),
.microsoft-email :deep([class*="content"]) {
  width: 100% !important;
  max-width: 100% !important;
  margin: 0 auto !important;
}

/* 微软邮件特定元素样式 - 新版本 */
.microsoft-email-new :deep(p) {
  margin: 12px 0;
  line-height: 1.6;
  color: #333333;
}

.microsoft-email-new :deep(h1), .microsoft-email-new :deep(h2), .microsoft-email-new :deep(h3) {
  color: #333333;
  font-weight: 600;
  margin-top: 20px;
  margin-bottom: 12px;
  line-height: 1.3;
}

.microsoft-email-new :deep(a) {
  color: #0078d4;
  text-decoration: none;
}

.microsoft-email-new :deep(a:hover) {
  text-decoration: underline;
}

.microsoft-email-new :deep(table) {
  border-collapse: collapse;
  width: 100% !important;
  max-width: 100% !important;
  margin: 16px 0;
  border-radius: 4px;
  overflow: hidden;
  box-shadow: none;
  table-layout: auto !important;
  border: none !important;
}

.microsoft-email-new :deep(td), .microsoft-email-new :deep(th) {
  padding: 10px 16px;
  border: none;
  border-bottom: 1px solid #ebeef5;
  text-align: left;
  vertical-align: top;
  width: auto !important;
  min-width: 100px;
  white-space: normal !important;
  word-break: break-word !important;
  word-wrap: break-word !important;
}

.microsoft-email-new :deep(tr:last-child) td {
  border-bottom: none;
}

.microsoft-email-new :deep(th) {
  background-color: #f5f7fa;
  font-weight: 600;
}

.microsoft-email-new :deep(ul), .microsoft-email-new :deep(ol) {
  padding-left: 2em;
  margin: 12px 0;
}

.microsoft-email-new :deep(li) {
  margin: 0.25em 0;
}

.microsoft-email-new :deep(img) {
  max-width: 100%;
  height: auto;
  display: block;
  margin: 16px auto;
  border-radius: 4px;
}

/* 修复验证码显示 - 新版本 */
.microsoft-email-new :deep(.verification-code),
.microsoft-email-new :deep([class*="verification"]),
.microsoft-email-new :deep([class*="code"]) {
  font-size: 24px !important;
  font-weight: 600 !important;
  color: #333333 !important;
  margin: 24px 0 !important;
  padding: 12px 0 !important;
  text-align: center !important;
  letter-spacing: 4px !important;
  display: block !important;
}

/* 强制所有div使用正确的宽度 - 新版本 */
.microsoft-email-new :deep(div) {
  max-width: 100% !important;
}

/* 修复微软邮件中的表格容器 - 新版本 */
.microsoft-email-new :deep([class*="container"]),
.microsoft-email-new :deep([class*="wrapper"]),
.microsoft-email-new :deep([class*="content"]) {
  width: 100% !important;
  max-width: 100% !important;
  margin: 0 auto !important;
  padding: 0 !important;
}

/* 修复Microsoft特有的样式问题 - 新版本 */
.microsoft-email-new :deep([class*="MsoNormal"]),
.microsoft-email-new :deep([class*="outlook"]),
.microsoft-email-new :deep([class*="microsoft"]),
.microsoft-email-new :deep([class*="x_"]) {
  max-width: 100% !important;
  width: auto !important;
  word-wrap: break-word !important;
  word-break: break-word !important;
  margin: 10px 0 !important;
  line-height: 1.6 !important;
  text-align: left !important;
}

/* Notion邮件特定样式 */
.notion-container {
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  box-sizing: border-box;
  overflow: hidden;
}

.notion-header {
  background-color: #000000;
  color: white;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  box-sizing: border-box;
  margin-bottom: 1px;
}

.notion-logo {
  height: 24px;
  width: 24px;
  flex-shrink: 0;
  margin-right: 8px;
}

.notion-title {
  font-size: 18px;
  font-weight: 600;
  color: white;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.notion-email {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  color: #333333;
  line-height: 1.5;
  word-wrap: break-word;
  background-color: white;
  padding: 20px;
  width: 100%;
  box-sizing: border-box;
}

.github-email :deep(h1), .github-email :deep(h2), .github-email :deep(h3) {
  color: #24292e;
  font-weight: 600;
  margin-top: 24px;
  margin-bottom: 16px;
  line-height: 1.25;
}

.github-email :deep(a) {
  color: #0366d6;
  text-decoration: none;
}

.github-email :deep(a:hover) {
  text-decoration: underline;
}

.github-email :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 16px 0;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.github-email :deep(td), .github-email :deep(th) {
  padding: 10px 16px;
  border: none;
  border-bottom: 1px solid #e1e4e8;
  text-align: left;
}

.github-email :deep(tr:last-child) td {
  border-bottom: none;
}

.github-email :deep(th) {
  background-color: #f6f8fa;
  font-weight: 600;
}

.github-email :deep(ul), .github-email :deep(ol) {
  padding-left: 2em;
}

.github-email :deep(li) {
  margin: 0.25em 0;
}

.github-email :deep(code) {
  font-family: SFMono-Regular, Consolas, Liberation Mono, Menlo, monospace;
  font-size: 85%;
  padding: 0.2em 0.4em;
  background-color: rgba(27, 31, 35, 0.05);
  border-radius: 3px;
}

.github-email :deep(pre) {
  background-color: #f6f8fa;
  border-radius: 6px;
  font-size: 85%;
  line-height: 1.45;
  overflow: auto;
  padding: 16px;
  margin: 16px 0;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

/* 未知格式邮件样式 */
.unknown-content {
  padding: 32px;
  text-align: center;
  background-color: #fff;
  border-radius: 8px;
  margin: 16px auto;
  max-width: 600px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.warning-text {
  color: #e6a23c;
  font-size: 16px;
  margin-bottom: 20px;
}

@media (max-width: 768px) {
  .email-content-viewer {
    padding: 0;
  }

  .email-header {
    padding: 16px;
    border-bottom: 1px solid #f0f0f0;
  }

  .subject h2 {
    font-size: 1.3rem;
    margin-bottom: 12px;
  }

  .email-content {
    padding: 0 16px;
    max-width: 100%;
  }

  .attachment-item {
    width: 100%;
  }

  .email-attachments {
    margin: 10px 16px;
    padding: 12px 16px;
    border-radius: 0;
    border-left: 2px solid #dcdfe6;
  }

  .header-item {
    flex-direction: row;
    align-items: flex-start;
  }

  .label {
    width: 60px;
    margin-bottom: 0;
    flex-shrink: 0;
  }

  .value {
    flex: 1;
  }

  .github-container, .microsoft-container, .notion-container, .microsoft-container-new, .default-container {
    max-width: 100%;
  }

  .github-email, .notion-email {
    font-size: 14px;
    padding: 16px;
  }

  .microsoft-email, .microsoft-email-new {
    font-size: 14px;
    padding: 16px;
    line-height: 1.5;
  }

  /* 微软邮件在移动端的特殊处理 - 旧版本 */
  .microsoft-email :deep(p) {
    margin: 10px 0;
  }

  .microsoft-email :deep(table) {
    margin: 12px 0;
    border: none;
  }

  .microsoft-email :deep(td), .microsoft-email :deep(th) {
    padding: 8px 12px;
  }

  .microsoft-email :deep([class*="button"]), .microsoft-email :deep([role="button"]) {
    display: block;
    width: 100%;
    margin: 12px 0;
  }

  /* 微软邮件在移动端的特殊处理 - 新版本 */
  .microsoft-email-new :deep(p) {
    margin: 10px 0;
  }

  .microsoft-email-new :deep(table) {
    margin: 12px 0;
    border: none;
  }

  .microsoft-email-new :deep(td), .microsoft-email-new :deep(th) {
    padding: 8px 12px;
  }

  .microsoft-email-new :deep([class*="button"]), .microsoft-email-new :deep([role="button"]) {
    display: block;
    width: 100%;
    margin: 12px 0;
  }

  .github-header, .notion-header {
    padding: 10px 16px;
  }

  .microsoft-header {
    padding: 10px 16px;
    background-color: #0078d4;
  }

  .github-logo, .notion-logo {
    height: 20px;
  }

  .microsoft-logo {
    height: 20px;
    width: auto;
  }

  .github-title, .notion-title, .microsoft-title {
    font-size: 16px;
    font-weight: 600;
  }

  .plain-content {
    font-size: 14px;
    max-width: 100%;
    padding: 16px 0;
  }

  .html-content :deep(table) {
    display: block;
    overflow-x: auto;
    white-space: nowrap;
    font-size: 14px;
    border: none;
    box-shadow: none;
  }

  .html-content :deep(td), .html-content :deep(th) {
    padding: 8px 12px;
    min-width: 80px;
    border-bottom: 1px solid #f0f0f0;
  }

  .html-content :deep(pre) {
    font-size: 13px;
    padding: 12px;
    overflow-x: auto;
    border: 1px solid #f0f0f0;
    box-shadow: none;
  }

  .html-content :deep(img) {
    max-width: 100%;
    height: auto;
  }

  /* 改善移动端的按钮样式 */
  .html-content :deep(.btn), .html-content :deep(.button) {
    display: block;
    width: 100%;
    text-align: center;
    padding: 10px 16px;
    border-radius: 2px;
  }

  /* 改善移动端的卡片样式 */
  .html-content :deep(.panel), .html-content :deep(.Box), .html-content :deep(.card) {
    padding: 16px;
    margin: 16px 0;
    border-radius: 0;
    border: 1px solid #f0f0f0;
    box-shadow: none;
  }

  /* 修复移动端垂直文本问题 */
  .html-content :deep([width]) {
    width: auto !important;
    max-width: 100% !important;
  }
}
</style>
