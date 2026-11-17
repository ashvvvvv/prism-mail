/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class', '[data-theme="espresso"]'],
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}'
  ],
  theme: {
    extend: {
      fontFamily: {
        display: [
          '"Instrument Serif"',
          '"Newsreader"',
          '"Noto Serif SC"',
          '"Songti SC"',
          'Georgia',
          'serif'
        ],
        serif: [
          '"Newsreader"',
          '"Noto Serif SC"',
          '"Instrument Serif"',
          '"Songti SC"',
          'Georgia',
          'serif'
        ],
        sans: [
          '"Inter"',
          '"PingFang SC"',
          '"HarmonyOS Sans SC"',
          '"Hiragino Sans GB"',
          '"Microsoft YaHei UI"',
          'system-ui',
          '-apple-system',
          'sans-serif'
        ],
        mono: [
          '"JetBrains Mono"',
          '"SF Mono"',
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Consolas',
          'monospace'
        ]
      }
    }
  },
  plugins: []
}
