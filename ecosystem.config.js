module.exports = {
  apps: [{
    name: 'consultant-it-bot',
    script: './server.js',
    instances: 1,
    exec_mode: 'fork',
    env: {
      NODE_ENV: 'production',
      PORT: 3000,
      // Эти переменные заставят Node.js использовать SOCKS5 прокси
      HTTP_PROXY: 'socks5://127.0.0.1:1080',
      HTTPS_PROXY: 'socks5://127.0.0.1:1080',
      NO_PROXY: 'localhost,127.0.0.1'
    }
  }]
};
