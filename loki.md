# 配置 mc 客户端（别名）
mc alias set myminio http://localhost:9000 admin changeit

# 创建 Loki 专用的 Access Key
mc admin user add myminio loki SuperSecretKey123456!

# 赋予读写权限
mc admin policy attach myminio readwrite --user loki

# 查看创建结果
mc admin user list myminio