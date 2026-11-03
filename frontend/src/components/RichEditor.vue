<template>
  <div :class="['rich-editor', { fullscreen: isFullscreen }]">
    <div class="rich-toolbar">
      <button type="button" :class="{ active: editor?.isActive('bold') }"
              @click="editor?.chain().focus().toggleBold().run()" title="Fett (Strg+B)">
        <strong>B</strong>
      </button>
      <button type="button" :class="{ active: editor?.isActive('italic') }"
              @click="editor?.chain().focus().toggleItalic().run()" title="Kursiv (Strg+I)">
        <em>I</em>
      </button>
      <button type="button" :class="{ active: editor?.isActive('underline') }"
              @click="editor?.chain().focus().toggleUnderline().run()" title="Unterstreichen (Strg+U)">
        <u>U</u>
      </button>
      <button type="button" :class="{ active: editor?.isActive('strike') }"
              @click="editor?.chain().focus().toggleStrike().run()" title="Durchgestrichen">
        <s>S</s>
      </button>
      <span class="sep"></span>
      <button type="button" :class="{ active: editor?.isActive('heading', { level: 2 }) }"
              @click="editor?.chain().focus().toggleHeading({ level: 2 }).run()" title="Überschrift 2">
        H2
      </button>
      <button type="button" :class="{ active: editor?.isActive('heading', { level: 3 }) }"
              @click="editor?.chain().focus().toggleHeading({ level: 3 }).run()" title="Überschrift 3">
        H3
      </button>
      <span class="sep"></span>
      <button type="button" :class="{ active: editor?.isActive('bulletList') }"
              @click="editor?.chain().focus().toggleBulletList().run()" title="Aufzählung">
        • Liste
      </button>
      <button type="button" :class="{ active: editor?.isActive('orderedList') }"
              @click="editor?.chain().focus().toggleOrderedList().run()" title="Nummerierung">
        1. Liste
      </button>
      <button type="button" :class="{ active: editor?.isActive('blockquote') }"
              @click="editor?.chain().focus().toggleBlockquote().run()" title="Zitat">
        ❝
      </button>
      <span class="sep"></span>
      <button type="button" @click="editor?.chain().focus().undo().run()" title="Rückgängig">
        ↶
      </button>
      <button type="button" @click="editor?.chain().focus().redo().run()" title="Wiederherstellen">
        ↷
      </button>
      <span class="sep"></span>
      <button type="button" @click="isFullscreen = !isFullscreen" :title="isFullscreen ? 'Vollbild verlassen' : 'Vollbild'">
        {{ isFullscreen ? '✕ Vollbild' : '⛶' }}
      </button>
    </div>
    <editor-content :editor="editor" class="rich-content" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'

const props = defineProps<{
  modelValue: string
  placeholder?: string
  minHeight?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const isFullscreen = ref(false)

const editor = useEditor({
  content: props.modelValue || '',
  extensions: [
    StarterKit,
    Underline,
  ],
  onUpdate: ({ editor }) => {
    emit('update:modelValue', editor.getHTML())
  },
})

watch(() => props.modelValue, (v) => {
  if (editor.value && v !== editor.value.getHTML()) {
    editor.value.commands.setContent(v || '', { emitUpdate: false })
  }
})

onBeforeUnmount(() => editor.value?.destroy())
</script>

<style scoped>
.rich-editor {
  border: 1px solid #ccc;
  border-radius: 4px;
  background: white;
  display: flex;
  flex-direction: column;
}
.rich-editor.fullscreen {
  position: fixed;
  inset: 0;
  z-index: 2000;
  border-radius: 0;
}
.rich-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  padding: 4px 6px;
  border-bottom: 1px solid #ddd;
  background: #fafafa;
  border-top-left-radius: 4px;
  border-top-right-radius: 4px;
}
.rich-toolbar button {
  background: white;
  border: 1px solid #ddd;
  padding: 4px 9px;
  cursor: pointer;
  font-size: 13px;
  border-radius: 3px;
  min-width: 28px;
}
.rich-toolbar button:hover { background: #efebe9; }
.rich-toolbar button.active { background: #5d4037; color: white; border-color: #3e2723; }
.sep { width: 1px; background: #ddd; margin: 2px 4px; }
.rich-content {
  min-height: 200px;
  padding: 12px 14px;
  font: 14px/1.6 'Calibri', 'Segoe UI', sans-serif;
  flex: 1;
  overflow: auto;
}
.rich-editor.fullscreen .rich-content {
  font-size: 16px;
  padding: 24px 60px;
}
.rich-content :deep(.ProseMirror) {
  min-height: 200px;
  outline: none;
}
.rich-content :deep(.ProseMirror p.is-editor-empty:first-child::before) {
  content: attr(data-placeholder);
  color: #aaa;
  pointer-events: none;
  height: 0;
  float: left;
}
.rich-content :deep(h2) { font-size: 18px; margin: 12px 0 6px; color: #3e2723; }
.rich-content :deep(h3) { font-size: 15px; margin: 10px 0 4px; color: #5d4037; }
.rich-content :deep(ul), .rich-content :deep(ol) { padding-left: 24px; margin: 6px 0; }
.rich-content :deep(blockquote) {
  border-left: 3px solid #5d4037;
  margin: 6px 0;
  padding: 4px 12px;
  color: #555;
  background: #fafafa;
}
.rich-content :deep(p) { margin: 4px 0; }
</style>
