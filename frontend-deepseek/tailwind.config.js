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
          '"Nunito"',
          '"M PLUS Rounded 1c"',
          '"Plus Jakarta Sans"',
          '"PingFang SC"',
          '"HarmonyOS Sans SC"',
          '"Hiragino Sans GB"',
          '"Microsoft YaHei UI"',
          'sans-serif'
        ],
        mono: [
          '"JetBrains Mono"',
          '"SF Mono"',
          'ui-monospace',
          'monospace'
        ]
      }
    },
  },
  plugins: [],
}
