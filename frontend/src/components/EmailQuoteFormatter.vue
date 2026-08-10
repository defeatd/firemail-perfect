<template>
  <div class="email-quote-formatter">
    <div v-if="formattedContent" v-html="formattedContent"></div>
    <div v-else class="original-content" v-html="sanitizedContent"></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import DOMPurify from 'dompurify'

const props = defineProps({
  content: {
    type: String,
    required: true
  },
  isHtml: {
    type: Boolean,
    default: false
  }
})

const formattedContent = ref('')
const sanitizedContent = computed(() => {
  return sanitizeHtml(props.content)
})

// 监听内容变化
watch(() => props.content, () => {
  processContent()
}, { immediate: true })

// 处理内容
const processContent = () => {
  if (!props.content) {
    formattedContent.value = ''
    return
  }
  
  if (props.isHtml) {
    processHtmlContent()
  } else {
    processPlainTextContent()
  }
}

// 处理HTML内容
const processHtmlContent = () => {
  let content = props.content
  
  // 检查是否包含引用
  if (content.includes('<blockquote') || content.includes('class="gmail_quote"')) {
    // 已经有格式化的引用，直接使用
    formattedContent.value = sanitizeHtml(content)
    return
  }
  
  // 尝试识别引用部分
  const quotePatterns = [
    { start: '-----Original Message-----', end: '' },
    { start: 'On ', end: ' wrote:' },
    { start: '在', end: '写道:' },
    { start: 'From:', end: '' }
  ]
  
  let foundQuote = false
  
  for (const pattern of quotePatterns) {
    const startIndex = content.indexOf(pattern.start)
    if (startIndex !== -1) {
      let endIndex = content.length
      if (pattern.end) {
        const endPos = content.indexOf(pattern.end, startIndex)
        if (endPos !== -1) {
          endIndex = endPos + pattern.end.length
        }
      }
      
      // 分割内容
      const mainContent = content.substring(0, startIndex).trim()
      const quoteHeader = content.substring(startIndex, endIndex).trim()
      const quoteContent = content.substring(endIndex).trim()
      
      // 创建格式化的HTML
      formattedContent.value = sanitizeHtml(`
        <div class="email-main-content">${mainContent}</div>
        <div class="email-quote">
          <div class="email-quote-header">${quoteHeader}</div>
          <div class="email-quote-content">${quoteContent}</div>
        </div>
      `)
      
      foundQuote = true
      break
    }
  }
  
  if (!foundQuote) {
    formattedContent.value = sanitizeHtml(content)
  }
}

// 处理纯文本内容
const processPlainTextContent = () => {
  let content = props.content
  
  // 检查是否包含引用行（以 > 开头）
  const lines = content.split('\n')
  let hasQuote = false
  let inQuote = false
  let formattedLines = []
  let currentQuote = []
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    
    // 检查是否是引用行
    if (line.trim().startsWith('>')) {
      hasQuote = true
      inQuote = true
      
      // 去除引用符号
      const cleanLine = line.replace(/^>+\s*/, '')
      currentQuote.push(cleanLine)
    } else if (inQuote && line.trim() === '') {
      // 空行，可能仍在引用中
      currentQuote.push('')
    } else {
      // 非引用行
      if (inQuote) {
        // 结束上一个引用块
        formattedLines.push(`<div class="email-quote">${currentQuote.join('<br>')}</div>`)
        currentQuote = []
        inQuote = false
      }
      
      formattedLines.push(line)
    }
  }
  
  // 处理最后的引用块
  if (inQuote && currentQuote.length > 0) {
    formattedLines.push(`<div class="email-quote">${currentQuote.join('<br>')}</div>`)
  }
  
  if (hasQuote) {
    formattedContent.value = sanitizeHtml(formattedLines.join('<br>'))
  } else {
    // 检查是否有其他类型的引用
    const quotePatterns = [
      { start: '-----Original Message-----', end: '' },
      { start: 'On ', end: ' wrote:' },
      { start: '在', end: '写道:' },
      { start: 'From:', end: '' }
    ]
    
    let foundQuote = false
    
    for (const pattern of quotePatterns) {
      const startIndex = content.indexOf(pattern.start)
      if (startIndex !== -1) {
        let endIndex = content.length
        if (pattern.end) {
          const endPos = content.indexOf(pattern.end, startIndex)
          if (endPos !== -1) {
            endIndex = endPos + pattern.end.length
          }
        }
        
        // 分割内容
        const mainContent = content.substring(0, startIndex).trim()
        const quoteHeader = content.substring(startIndex, endIndex).trim()
        const quoteContent = content.substring(endIndex).trim()
        
        // 创建格式化的HTML
        formattedContent.value = sanitizeHtml(`
          <div class="email-main-content">${mainContent.replace(/\n/g, '<br>')}</div>
          <div class="email-quote">
            <div class="email-quote-header">${quoteHeader.replace(/\n/g, '<br>')}</div>
            <div class="email-quote-content">${quoteContent.replace(/\n/g, '<br>')}</div>
          </div>
        `)
        
        foundQuote = true
        break
      }
    }
    
    if (!foundQuote) {
      // 没有找到引用，直接转换换行符
      formattedContent.value = sanitizeHtml(content.replace(/\n/g, '<br>'))
    }
  }
}

// 净化HTML内容，防止XSS攻击
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
      'strike', 'sub', 'sup'
    ],
    ALLOWED_ATTR: [
      'href', 'target', 'src', 'alt', 'style', 'class', 'id', 'width', 'height',
      'align', 'valign', 'bgcolor', 'border', 'cellpadding', 'cellspacing',
      'color', 'colspan', 'dir', 'face', 'frame', 'frameborder', 'headers',
      'hspace', 'lang', 'marginheight', 'marginwidth', 'nowrap', 'rel',
      'rev', 'rowspan', 'scrolling', 'shape', 'span', 'summary', 'title',
      'usemap', 'vspace', 'start', 'type', 'value', 'size', 'data-*'
    ]
  })
}
</script>

<style>
.email-quote-formatter {
  width: 100%;
}

.email-quote {
  margin: 16px 0;
  padding: 12px;
  background-color: #f5f7fa;
  border-left: 4px solid #dcdfe6;
  color: #606266;
  font-size: 0.95em;
}

.email-quote-header {
  font-weight: 500;
  margin-bottom: 8px;
  color: #909399;
}

.email-quote-content {
  white-space: pre-line;
}

.email-main-content {
  margin-bottom: 16px;
}
</style>
