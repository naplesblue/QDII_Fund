# VPS 部署与维护

仓库：https://github.com/naplesblue/QDII_Fund

站点：https://fund.naplesblue.cn

运行环境：Linux、Python 3.10+、curl、Git、Nginx、systemd；无第三方 Python 依赖。服务监听 `127.0.0.1:8765`，仅由 Nginx 反代公开。使用 `fund-atlas` 系统账户，不能用 root 运行应用。

## 目录

- `/opt/fund-atlas/repo`：Git 克隆，用于拉取提交。
- `/opt/fund-atlas/releases/<commit>`：从指定提交导出的代码。
- `/opt/fund-atlas/current`：当前版本软链接。
- `/var/lib/fund-atlas`：运行快照、SQLite 缓存、锁和原始响应；升级代码不得覆盖。
- `/etc/systemd/system/fund-atlas.service`：后台服务。
- `/etc/nginx/sites-available/fund-atlas`：本站反代与证书配置。

## 首次安装

在 VPS 以 root 执行以下命令；仓库公开，无须复制个人 GitHub 或 SSH 凭据。

```sh
useradd --system --user-group --home-dir /var/lib/fund-atlas --shell /usr/sbin/nologin fund-atlas
install -d -m 755 /opt/fund-atlas/releases
install -d -o fund-atlas -g fund-atlas -m 750 /var/lib/fund-atlas
git clone https://github.com/naplesblue/QDII_Fund.git /opt/fund-atlas/repo
install -m 644 /opt/fund-atlas/repo/deploy/fund-atlas.service /etc/systemd/system/fund-atlas.service
systemctl daemon-reload
sh /opt/fund-atlas/repo/deploy/release.sh <完整提交哈希>
systemctl enable fund-atlas
```

可在首次启动前将经过核验的本地 `work/runtime/data.json` 复制到 `/var/lib/fund-atlas/data.json`，并将所有者设为 `fund-atlas:fund-atlas`。这只是初始数据迁移，不进入 Git；缓存以原获取时间初始化，不会将旧数据伪装为新获取。后续部署不要重复覆盖。

安装 `nginx.conf.example` 为独立站点配置，链接到 `sites-enabled`；先运行 `nginx -t`，通过后再 reload。保留现有站点。确认 DNS 指向 VPS 后，用已有 certbot 配置为 `fund.naplesblue.cn` 签发证书并开启 HTTP → HTTPS 跳转，例如 `certbot --nginx -d fund.naplesblue.cn --redirect`。模板只有 HTTP，正式部署的 TLS 配置由 certbot 管理。

## 更新和回滚

先在本地运行 README 中的验证，再提交并 push。VPS：

```sh
git -C /opt/fund-atlas/repo fetch origin main
sh /opt/fund-atlas/repo/deploy/release.sh <已验证的完整提交哈希>
```

脚本使用独立临时数据目录运行离线测试，切换版本、重启，并检查后端；启动失败自动切回上个代码版本。回滚也使用同一脚本，传入旧提交哈希。回滚前确认旧版本兼容当前数据格式；脚本不会回滚运行数据。修改 systemd 模板后需要重新 install、daemon-reload；Nginx 配置修改后需要 `nginx -t` 再 reload。

## 检查和日志

```sh
systemctl status fund-atlas --no-pager
journalctl -u fund-atlas -n 80 --no-pager
curl --fail https://fund.naplesblue.cn/api/status
nginx -t
certbot certificates
systemctl list-timers --all | grep certbot
```

`/api/status` 中 `running: false` 表示当前没有刷新任务。网页刷新只检查共享缓存，到期才访问上游；单项失败有冷却。`collector.enabled` 表示溢价定时采集已启用，`last_attempt`/`last_success`/`last_archived` 分别记录请求尝试、成功和有效样本落库时间；检查 `error` 和 `history_error` 可定位失败。不要在服务运行时另起 `--refresh` 进程，同一运行目录有进程锁。

## 数据和备份

收藏在各用户浏览器 localStorage 中；网站数据和冷却在服务器共享。Nginx/CDN 不应缓存 `/api/` 或 `/data.json`。数据日期与获取时间是不同概念。

备份时短暂停止服务，将 `/var/lib/fund-atlas` 完整备份到私有位置后再启动，确保 JSON 与 SQLite 一致；恢复同样先停止服务并恢复文件权限。运行数据、备份和 SSH 密钥不得提交仓库。原始响应位于 `evidence/`，应按磁盘容量定期检查。

当前交易日历仅覆盖 2026 年，应在 2027 年前根据交易所公告更新；未知年份会阻止行情请求。接口无可用性保证，休市快照不保证等于官方收盘值。所有指标口径以根目录 README 为准。

## 溢价定时采集

服务模板的 `FUND_COLLECT_PREMIUM=1` 启用进程内采集，无须另加 cron。更新此功能必须重新安装 systemd 模板并执行 `systemctl daemon-reload`，再运行 release.sh；仅更新代码不会改变已有服务环境。历史在 `/var/lib/fund-atlas/premium-history.sqlite3`，与当前失败清空策略独立，备份应覆盖该文件。休市无自动上游请求；共享缓存到期才获取，手动任务持锁时跳过。关闭时将环境变量改为 0 并重启。
