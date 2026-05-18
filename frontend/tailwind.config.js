/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        surface: 'rgba(255,255,255,0.05)',
        navy: {
          DEFAULT: '#080c1a',
          800: '#0d1225',
          700: '#111827',
        },
      },
      backgroundImage: {
        'gradient-accent': 'linear-gradient(135deg, #7c3aed, #06b6d4)',
      },
      animation: {
        'fade-in':    'fadeIn 0.2s ease-out',
        'slide-down': 'slideDown 0.2s cubic-bezier(0.16,1,0.3,1)',
        'pulse-slow': 'pulse 3s ease-in-out infinite',
      },
      keyframes: {
        fadeIn:    { from: { opacity: '0', transform: 'translateY(8px)' },  to: { opacity: '1', transform: 'translateY(0)' } },
        slideDown: { from: { opacity: '0', transform: 'translateY(-6px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
      },
      boxShadow: {
        'glass':  '0 4px 24px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.06)',
        'glow-violet': '0 0 20px rgba(124,58,237,0.25)',
        'glow-urgent': '0 0 16px rgba(239,68,68,0.2)',
      },
    },
  },
  plugins: [],
};
