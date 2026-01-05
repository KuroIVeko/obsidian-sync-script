# Obsidian Livesync to Local Markdown Sync
>这是一个轻量级的 Python 服务，专为配合 obsidian-livesync 插件使用。  
>它运行在 Docker 容器中，实时监听你的 CouchDB 数据库变化，并将指定的 Obsidian 文件夹（例如 "Blog"）单向同步导出为本地的标准 Markdown 文件。  
>最佳用途： 将 Obsidian 作为 CMS，通过此脚本实时同步内容到 Hugo/Hexo/Jekyll 等静态博客生成器的 content 目录，实现“在 Obsidian 写作，博客自动更新”。  
> ✨ 功能特性
>* ⚡️ 实时响应：利用 CouchDB 的 _changes 流，实现毫秒级的同步延迟。
>* 📂 目录结构保持：完美还原 Obsidian 中的文件夹层级。🗑 自动清理：当你在 Obsidian 删除文件或移动目录时，本地对应的文件/空目录也会自动删除。
>* 🎯 过滤机制：支持指定 TARGET_FOLDER（如只同步 Blog/ 目录下的文章），忽略库中其他无关笔记。🛡 文件保护：内置保护机制，不会误删 _index.md 或 .gitignore 等博客系统的元数据文件。
>* 🐳 Docker 部署：基于 Alpine Linux，镜像体积小，部署简单。

## 🚀 快速开始 (Docker Compose)这是最推荐的部署方式。你可以将其与你的 CouchDB 服务编排在同一个 docker-compose.yml 文件中。
### 1. 目录挂载说明你需要将宿主机上的博客内容目录挂载到容器的 /blog_root/content/posts (或脚本中定义的路径)。
### 2. Docker Compose 配置示例如果你直接使用本仓库构建好的镜像（假设你已推送到 GHCR）：YAMLversion: '3.8'

```
services:
  # 你的同步服务
  obsidian_sync:
    image: ghcr.io/你的用户名/obsidian-sync-script:latest
    container_name: obsidian_sync
    restart: unless-stopped
    depends_on:
      - obsidian_livesync
    environment:
      # --- 数据库连接配置 ---
      - DB_HOST=obsidian_livesync  # CouchDB 容器的服务名
      - DB_NAME=vault              # Livesync 的数据库名，默认为 vault
      - DB_USER=admin              # 你的 CouchDB 用户名
      - DB_PASS=password           # 你的 CouchDB 密码
      
      # --- 同步配置 ---
      - TARGET_FOLDER=Blog         # 只同步 Obsidian 中这个文件夹下的内容
      - INTERVAL=20                # 轮询保底间隔 (秒)
    volumes:
      # [重要] 将容器内的输出目录映射到你宿主机的博客目录
      # 格式: /宿主机路径:/容器内路径
      # 注意：脚本默认向 /blog_root/content/posts 写入
      - /opt/hugo/myblog/content/posts:/blog_root/content/posts
```
```
  # (可选) 你的 CouchDB 服务，如果还没有的话
  obsidian_livesync:
    image: couchdb:3.5.1
    container_name: obsidian_livesync
    restart: unless-stopped
    environment:
      - COUCHDB_USER=admin
      - COUCHDB_PASSWORD=password
    volumes:
      - ./couchdb_data:/opt/couchdb/data
      - ./local.ini:/opt/couchdb/etc/local.ini
```

### 3. 环境变量说明变量名默认值说明
| 变量名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| **DB_HOST** | `obsidian_livesync` | CouchDB 的地址或容器服务名 |
| **DB_NAME** | `vault` | 你的 Obsidian 库在 CouchDB 中的名称 |
| **DB_USER** | - | 数据库用户名 |
| **DB_PASS** | - | 数据库密码 |
| **TARGET_FOLDER** | `Blog` | **关键**：指定 Obsidian 中需要同步的根文件夹名称 |
| **INTERVAL** | `20` | 当实时流断开时的重连/轮询间隔（秒） |

⚠️ 注意事项
1. CouchDB访问：为了简化脚本逻辑，该脚本通过容器名来直接寻址，这意味着该脚本**必须**得与CouchDB放在同一虚拟网桥下，且该虚拟网桥**必须**开启了driver: bridge（Docker Compose 默认即为此模式），同时CouchDB在容器**内部**的监听端口也**必须**保持为 `5984`（*注意：你依然可以将 CouchDB 的宿主机端口映射为其他（如 15984:5984），这不影响本脚本在容器网络内部的连接。*）。
2. 单向同步：本脚本是单向的（CouchDB -> 本地文件）。请不要在本地直接修改生成的 Markdown 文件，因为下一次同步时它们会被覆盖。所有的编辑操作都应在 Obsidian 中完成。
3. 图片处理：脚本目前包含基础的 Base64 图片解码逻辑，但建议配合图床使用，以保持 Markdown 文件的纯净。
4. 受保护文件：脚本会忽略并保留本地目录下的 _index.md (Hugo 列表页配置) 和 .gitignore 文件，不会将其删除。

🤝 贡献欢迎提交 Issue 或 Pull Request 来改进代码逻辑！Created with ❤️ by [Suyurine]
