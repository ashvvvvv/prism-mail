/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          '"Inter"',
          '"Plus Jakarta Sans"',
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
    },
  },
  plugins: [],
}
