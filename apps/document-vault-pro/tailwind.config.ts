import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        navy: '#07162f',
        royal: '#246BFE',
        emerald: '#10B981'
      },
      boxShadow: { glow: '0 0 60px rgba(36,107,254,.35)' },
      keyframes: { float: { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-14px)' } } },
      animation: { float: 'float 8s ease-in-out infinite' }
    }
  },
  plugins: []
};
export default config;
