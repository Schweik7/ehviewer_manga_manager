"""漫画管理器主类 - 协调ADB、数据库和文件系统操作。"""

import os
import shutil
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

from .adb_manager import ADBManager
from .config import DOWNLOAD_DIR, SPIDER_INFO_FILENAME, DEFAULT_THRESHOLD, STATE_NAMES
from .database import MangaDatabase
from .filename_utils import sanitize_filename, needs_sanitization, make_name_mapping_note
from .spider_info import SpiderInfo


class MangaManager:
    """漫画管理器主类"""

    def __init__(self):
        self.adb = ADBManager()
        self.db: Optional[MangaDatabase] = None
        self.temp_db_path = "temp_ehviewer.db"
        self.backup_db_path: Optional[str] = None
        self._phone_dirs: Optional[set] = None
        # 当前加载的数据库来源描述 (供界面/日志显示)
        self.loaded_db_source: Optional[str] = None

    # ------------------------------------------------------------------
    # 初始化 / 清理
    # ------------------------------------------------------------------

    def initialize(
        self,
        remote_db_filename: Optional[str] = None,
        local_db_file: Optional[str] = None,
    ) -> bool:
        """连接设备并加载数据库。

        Args:
            remote_db_filename: 指定手机导出目录中的数据库文件名;
                                None 时自动选最新的 EhViewer 原生导出。
            local_db_file:      改用电脑上的本地数据库文件 (优先级高于 remote);
                                仍需连接设备以便后续比对手机目录/迁移。
        """
        if not self.adb.check_adb():
            return False
        if not self.adb.check_device():
            return False

        if local_db_file:
            try:
                shutil.copy2(local_db_file, self.temp_db_path)
            except OSError as e:
                print(f"读取本地数据库失败: {e}")
                return False
            self.loaded_db_source = f"本地文件: {os.path.basename(local_db_file)}"
            print(f"使用本地数据库文件: {local_db_file}")
        else:
            if not self.adb.pull_exported_database(self.temp_db_path, remote_db_filename):
                return False
            self.loaded_db_source = remote_db_filename or "自动(最新原生导出)"

        self.db = MangaDatabase(self.temp_db_path)
        if not self.db.connect():
            return False

        return True

    def list_available_databases(self) -> List[str]:
        """列出手机上可选的导出数据库 (供界面/CLI 让用户手动选择)。"""
        return self.adb.list_exported_databases()

    def cleanup(self):
        if self.db:
            self.db.close()
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # 手机目录列表 (一次性拉取并缓存, 避免逐条 adb 往返)
    # ------------------------------------------------------------------

    def get_phone_dir_set(self, refresh: bool = False) -> set:
        """
        返回手机下载目录中所有漫画目录名的集合 (一次 adb 调用)。

        旧实现对每条数据库记录执行一次 `adb shell test -d`, 500+ 条记录
        意味着 500+ 次 adb 往返, 耗时数分钟; 且 `test -d "$dir"` 对含 `"`
        `$` 的目录名会出错。改为一次 `ls -1` 取全部目录名做内存集合比对,
        既快又稳健。结果缓存, 多次分析复用。
        """
        if self._phone_dirs is None or refresh:
            self._phone_dirs = set(self.adb.list_manga_dirs())
        return self._phone_dirs

    # ------------------------------------------------------------------
    # 阅读进度分析
    # ------------------------------------------------------------------

    def analyze_reading_progress(
        self, threshold: float = DEFAULT_THRESHOLD
    ) -> List[Dict]:
        """分析所有漫画的阅读进度, 返回超过阈值的列表。"""
        assert self.db is not None
        downloads = self.db.get_all_downloads()

        phone_dirs = self.get_phone_dir_set()

        results = []
        print(f"\n开始分析 {len(downloads)} 个下载项的阅读进度...")
        print(f"阅读进度阈值: {threshold * 100:.0f}%\n")

        for dl in downloads:
            gid = dl["gid"]
            title = dl["title"]
            state = dl["state"]

            dirname = self.db.get_download_dirname(gid) or f"{gid}-{dl['token']}"

            if dirname not in phone_dirs:
                print(f"  [跳过] {title} — 手机上目录不存在")
                continue

            temp_dir = f"temp_manga_{gid}"
            os.makedirs(temp_dir, exist_ok=True)

            spider_info_path = os.path.join(temp_dir, SPIDER_INFO_FILENAME)
            remote_path = f"{DOWNLOAD_DIR}/{dirname}/{SPIDER_INFO_FILENAME}"

            try:
                ok = self.adb.pull_single_file(remote_path, spider_info_path)

                if not ok or not os.path.exists(spider_info_path):
                    print(f"  [失败] {title} — 无法读取阅读进度文件")
                    continue

                spider = SpiderInfo(spider_info_path)
                if spider.read():
                    progress = spider.get_read_progress()
                    state_text = STATE_NAMES.get(state, "未知")

                    info = {
                        "gid": gid,
                        "title": title,
                        "dirname": dirname,
                        "current_page": spider.start_page,
                        "total_pages": spider.pages,
                        "progress": progress,
                        "state": state,
                        "state_text": state_text,
                    }

                    if progress >= threshold:
                        results.append(info)
                        print(
                            f"  [达标] {title}"
                            f" {progress*100:.1f}%"
                            f" ({spider.start_page + 1}/{spider.pages})"
                            f" 状态:{state_text}"
                        )
                    else:
                        print(
                            f"  [未达] {title}"
                            f" {progress*100:.1f}%"
                            f" ({spider.start_page + 1}/{spider.pages})"
                        )
                else:
                    print(f"  [失败] {title} — 解析进度文件失败")

            except Exception as e:
                print(f"  [错误] {title} — {e}")
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        return results

    # ------------------------------------------------------------------
    # 漫画移动
    # ------------------------------------------------------------------

    def _resolve_local_dirname(self, remote_dirname: str) -> tuple[str, bool]:
        """
        将手机上的目录名转换为本地安全的目录名。

        Returns:
            (local_dirname, was_sanitized)
        """
        local_dirname = sanitize_filename(remote_dirname)
        was_sanitized = local_dirname != remote_dirname
        return local_dirname, was_sanitized

    def move_manga_to_pc(
        self,
        manga_info: Dict,
        dest_dir: str,
        remove_from_phone: bool = False,
        dry_run: bool = False,
    ) -> bool:
        """
        将单个漫画从手机拉取到电脑。

        文件名净化策略:
        - remote_dirname 用于 adb pull 的源路径 (Android路径, 允许特殊字符)
        - local_dirname  是净化后的本地目录名 (确保Windows兼容)
        - 若两者不同, 会额外记录映射关系到 dest_dir/name_mapping.txt

        Args:
            manga_info:       analyze_reading_progress 返回的漫画信息字典
            dest_dir:         本地目标根目录
            remove_from_phone: 成功拉取后是否删除手机上的原文件
            dry_run:          仅打印操作计划, 不执行实际操作
        """
        remote_dirname = manga_info["dirname"]
        title = manga_info["title"]
        local_dirname, was_sanitized = self._resolve_local_dirname(remote_dirname)
        local_dest_path = os.path.join(dest_dir, local_dirname)

        print(f"\n  标题: {title}")
        print(f"  进度: {manga_info['progress']*100:.1f}%")
        print(f"  手机目录: {remote_dirname}")
        if was_sanitized:
            print(f"  本地目录: {local_dirname}  [已净化文件名]")
        else:
            print(f"  本地目录: {local_dirname}")

        if dry_run:
            print("  [DRY-RUN] 跳过实际操作")
            return True

        if os.path.exists(local_dest_path):
            print(f"  [跳过] 本地已存在: {local_dest_path}")
            return True

        if not self.adb.pull_manga(remote_dirname, local_dest_path):
            return False

        # 记录文件名映射 (供日后参考)
        if was_sanitized:
            self._append_name_mapping(dest_dir, remote_dirname, local_dirname)

        if remove_from_phone:
            if self.adb.remove_manga_dir(remote_dirname):
                # 同步更新缓存, 使本次会话后续的失效记录扫描保持准确
                if self._phone_dirs is not None:
                    self._phone_dirs.discard(remote_dirname)
            else:
                print("  [警告] 删除手机文件失败, 请手动清理")

        return True

    @staticmethod
    def _append_name_mapping(dest_dir: str, original: str, sanitized: str):
        """将文件名映射追加到 name_mapping.txt。"""
        mapping_file = os.path.join(dest_dir, "name_mapping.txt")
        line = f"{sanitized}\t<--\t{original}\n"
        try:
            with open(mapping_file, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass  # 映射记录不影响主流程

    # ------------------------------------------------------------------
    # 数据库清理
    # ------------------------------------------------------------------

    def clean_database_records(self, gid_list: List[int]) -> int:
        """清理数据库中指定GID的记录, 返回成功删除数量。"""
        assert self.db is not None
        if not gid_list:
            return 0

        print(f"\n正在清理 {len(gid_list)} 个漫画的数据库记录...")
        deleted_count = 0
        for gid in gid_list:
            if self.db.delete_download_by_gid(gid):
                deleted_count += 1
                print(f"  已删除记录 GID={gid}")
            else:
                print(f"  删除失败 GID={gid}")

        return deleted_count

    def find_missing_manga(self) -> List[Dict]:
        """
        查找数据库中存在但手机上不存在的漫画 (失效记录)。

        典型场景: 用户导入/恢复了一个旧的数据库备份, 其中包含的漫画早已
        被本工具迁移走或在手机上手动删除, 导致数据库里残留大量指向不存在
        目录的"失效记录"。本方法一次性列出手机目录做集合比对, 快速定位。
        """
        assert self.db is not None
        downloads = self.db.get_all_downloads()
        phone_dirs = self.get_phone_dir_set()
        missing = []
        print(f"\n开始检查 {len(downloads)} 个下载项 (手机现有 {len(phone_dirs)} 个目录)...")

        for dl in downloads:
            gid = dl["gid"]
            title = dl["title"]
            dirname = self.db.get_download_dirname(gid) or f"{gid}-{dl['token']}"

            if dirname not in phone_dirs:
                state_text = STATE_NAMES.get(dl["state"], "未知")
                missing.append(
                    {
                        "gid": gid,
                        "title": title,
                        "dirname": dirname,
                        "state": dl["state"],
                        "state_text": state_text,
                    }
                )

        print(f"  发现 {len(missing)} 条失效记录 (手机上目录已不存在)")
        return missing

    # ------------------------------------------------------------------
    # 数据库备份与推送
    # ------------------------------------------------------------------

    def create_backup_and_push(self) -> bool:
        """备份当前数据库并推送到手机。"""
        assert self.db is not None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_db_path = f"ehviewer_backup_{timestamp}.db"

        print("\n正在备份数据库...")
        if not self.db.backup(self.backup_db_path):
            return False

        return self.adb.push_database_to_phone(self.temp_db_path)

    # ------------------------------------------------------------------
    # 文件名安全预检
    # ------------------------------------------------------------------

    def preview_filename_issues(self) -> List[Dict]:
        """
        预扫描所有漫画目录名, 列出在Windows上需要净化的条目。
        不连接手机, 直接分析数据库中的dirname字段。
        """
        assert self.db is not None
        downloads = self.db.get_all_downloads()
        issues = []

        for dl in downloads:
            gid = dl["gid"]
            dirname = self.db.get_download_dirname(gid) or f"{gid}-{dl['token']}"
            if needs_sanitization(dirname):
                safe = sanitize_filename(dirname)
                issues.append(
                    {
                        "gid": gid,
                        "title": dl["title"],
                        "original": dirname,
                        "sanitized": safe,
                    }
                )

        return issues
