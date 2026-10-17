# 本地Dify运行说明

本机使用已存在的Dify 1.11.4 Docker Compose实例，详见[企业部署记录](../enterprise/README.md)。容器包括API、Web、Worker、Worker Beat、PostgreSQL、Redis、Sandbox、插件服务、Weaviate及Nginx。业务MySQL独立于Dify内部PostgreSQL。

查看本机实例：

```powershell
docker compose -f D:\dify-1.11.4\dify-1.11.4\docker\docker-compose.yaml ps
```

若手动停止过Dify，可在该Compose目录使用现有配置`docker compose up -d`恢复；保留其原`.env`和volumes。本项目没有复制含真实凭据的完整Compose，也没有把已有部署重建为第二套实例。Docker Desktop须先运行。

官方部署资料：[Dify源码及部署说明](https://github.com/langgenius/dify/tree/1.11.4/docker)。
