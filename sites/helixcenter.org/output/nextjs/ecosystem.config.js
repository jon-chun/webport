module.exports = {
  apps: [
    {
      name: "helixcenter",
      script: "node_modules/.bin/next",
      args: "start",
      instances: "max",
      exec_mode: "cluster",
      env: {
        NODE_ENV: "production",
        PORT: 3000,
      },
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      error_file: "/var/log/pm2/helixcenter-error.log",
      out_file: "/var/log/pm2/helixcenter-out.log",
      merge_logs: true,
      max_memory_restart: "500M",
    },
  ],
};
