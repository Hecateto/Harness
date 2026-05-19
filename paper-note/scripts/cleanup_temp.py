#!/usr/bin/env python3
"""
Cleanup temporary files for paper-note skill.

This script removes temporary files created during paper note generation.
It is designed to be called automatically at the end of the workflow.
"""

from __future__ import annotations

import sys
import logging
import argparse
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Tuple, Optional


# Local imports
from config import (
    __version__,
    load_config,
    setup_logging,
    PaperNoteConfig,
    DEFAULT_TEMP_FILE_PATTERNS,
    PROTECTED_EXTENSIONS,
)


# =============================================================================
# File Checker Classes (Chain of Responsibility Pattern)
# =============================================================================

class FileChecker(ABC):
    """
    抽象文件检查器基类
    
    定义了文件安全检查的统一接口。每个具体检查器负责一个特定的验证规则，
    并返回 Optional[bool] 表示检查结果：
    - True: 文件可以安全删除
    - False: 文件不能删除
    - None: 继续执行下一个检查器
    """
    
    @abstractmethod
    def check(self, file_path: Path, logger: logging.Logger) -> Optional[bool]:
        """
        检查文件是否符合特定条件
        
        Args:
            file_path: 要检查的文件路径
            logger: 日志记录器
            
        Returns:
            True 表示可以删除，False 表示不能删除，None 表示继续检查
        """
        pass


class ExistenceChecker(FileChecker):
    """
    文件存在性检查器
    
    检查文件是否存在，不存在的文件不能被删除。
    """
    
    def check(self, file_path: Path, logger: logging.Logger) -> Optional[bool]:
        """
        检查文件是否存在
        
        Args:
            file_path: 要检查的文件路径
            logger: 日志记录器
            
        Returns:
            False 如果文件不存在，None 如果文件存在
        """
        if not file_path.exists():
            logger.debug(f"File does not exist: {file_path}")
            return False
        return None


class FileTypeChecker(FileChecker):
    """
    文件类型检查器
    
    确保路径指向的是文件而非目录，目录不能被删除。
    """
    
    def check(self, file_path: Path, logger: logging.Logger) -> Optional[bool]:
        """
        检查路径是否为文件
        
        Args:
            file_path: 要检查的文件路径
            logger: 日志记录器
            
        Returns:
            False 如果不是文件，None 如果是文件
        """
        if not file_path.is_file():
            logger.debug(f"Skipping non-file: {file_path}")
            return False
        return None


class ProtectedExtensionChecker(FileChecker):
    """
    受保护扩展名检查器
    
    检查文件扩展名是否在受保护列表中，受保护的文件类型不能被删除。
    支持配置允许例外（如 .txt 文件）。
    """
    
    def __init__(
        self, 
        protected_extensions: set[str], 
        allowed_extensions: Optional[set[str]] = None
    ) -> None:
        """
        初始化受保护扩展名检查器
        
        Args:
            protected_extensions: 受保护的扩展名集合
            allowed_extensions: 允许例外的扩展名集合（即使受保护也可以删除）
        """
        self.protected_extensions = protected_extensions
        self.allowed_extensions = allowed_extensions or set()
    
    def check(self, file_path: Path, logger: logging.Logger) -> Optional[bool]:
        """
        检查文件扩展名是否受保护
        
        Args:
            file_path: 要检查的文件路径
            logger: 日志记录器
            
        Returns:
            False 如果扩展名受保护且不在允许列表中，None 否则
        """
        ext = file_path.suffix.lower()
        if ext in self.protected_extensions and ext not in self.allowed_extensions:
            logger.warning(f"Skipping protected file type: {file_path}")
            return False
        return None


class TempFilePatternChecker(FileChecker):
    """
    临时文件模式匹配检查器
    
    检查文件名是否匹配已知的临时文件模式或包含临时文件指示器。
    匹配的文件被认为是临时文件，可以安全删除。
    """
    
    def __init__(
        self, 
        temp_patterns: List[str], 
        temp_indicators: List[str]
    ) -> None:
        """
        初始化临时文件模式检查器
        
        Args:
            temp_patterns: 临时文件的 glob 模式列表
            temp_indicators: 临时文件名中常见的指示器字符串列表
        """
        self.temp_patterns = temp_patterns
        self.temp_indicators = temp_indicators
    
    def check(self, file_path: Path, logger: logging.Logger) -> Optional[bool]:
        """
        检查文件是否匹配临时文件模式
        
        Args:
            file_path: 要检查的文件路径
            logger: 日志记录器
            
        Returns:
            True 如果匹配临时文件模式，None 如果不匹配
        """
        filename = file_path.name.lower()
        ext = file_path.suffix.lower()
        
        # 检查文件名是否匹配已知的临时文件模式
        for pattern in self.temp_patterns:
            if Path(file_path.name).match(pattern):
                return True
        
        # 对于 .txt 文件，检查文件名是否包含临时文件指示器
        if ext == ".txt":
            for indicator in self.temp_indicators:
                if indicator in filename:
                    return True
        
        return None


class DefaultSafetyChecker(FileChecker):
    """
    默认安全检查器
    
    作为责任链的最后一环，对于未能匹配任何已知模式的文件，
    采取保守策略，拒绝删除并发出警告。
    """
    
    def check(self, file_path: Path, logger: logging.Logger) -> Optional[bool]:
        """
        对未知文件执行默认安全检查
        
        Args:
            file_path: 要检查的文件路径
            logger: 日志记录器
            
        Returns:
            始终返回 False，表示不能安全删除
        """
        logger.warning(f"Potentially unsafe file (not a known temp pattern): {file_path}")
        return False


# =============================================================================
# Main Safety Check Function
# =============================================================================

def is_safe_to_delete(file_path: Path, logger: logging.Logger) -> bool:
    """
    检查文件是否可以安全删除（使用责任链模式）
    
    通过一系列检查器按顺序执行安全检查：
    1. 文件存在性检查
    2. 文件类型检查（确保是文件而非目录）
    3. 受保护扩展名检查
    4. 临时文件模式匹配检查
    5. 默认安全检查（对未知文件采取保守策略）
    
    Args:
        file_path: 要检查的文件路径
        logger: 日志记录器
        
    Returns:
        True 表示可以安全删除，False 表示不能删除
    """
    # 构建检查器链
    checkers: List[FileChecker] = [
        ExistenceChecker(),
        FileTypeChecker(),
        ProtectedExtensionChecker(PROTECTED_EXTENSIONS, {".txt"}),
        TempFilePatternChecker(
            DEFAULT_TEMP_FILE_PATTERNS, 
            ["temp", "tmp", "paper_note", ".extracted"]
        ),
        DefaultSafetyChecker()
    ]
    
    # 按顺序执行检查，任一检查器返回非 None 结果即终止链
    for checker in checkers:
        result = checker.check(file_path, logger)
        if result is not None:
            return result
    
    # 理论上不会执行到这里（DefaultSafetyChecker 总是返回 False）
    return False


def cleanup_files(
    file_paths: Optional[List[Path]] = None,
    patterns: Optional[List[str]] = None,
    dry_run: bool = False,
    recursive: bool = False,
    config: Optional[PaperNoteConfig] = None,
    logger: Optional[logging.Logger] = None,
) -> Tuple[List[Path], List[Tuple[Path, str]]]:
    """
    Clean up temporary files.
    
    Args:
        file_paths: Optional list of specific files to clean up
        patterns: Optional list of glob patterns to match (defaults to DEFAULT_TEMP_FILE_PATTERNS)
        dry_run: If True, don't actually delete files
        recursive: If True, search recursively in subdirectories
        config: Configuration object (optional, uses defaults if not provided)
        logger: Logger instance (optional, creates new if not provided)
        
    Returns:
        Tuple of (list of cleaned files, list of (file path, error message) tuples)
    """
    if config is None:
        config = load_config()
    
    if logger is None:
        logger = setup_logging(config.logging)
    
    if patterns is None:
        patterns = DEFAULT_TEMP_FILE_PATTERNS
    
    files_to_cleanup: List[Path] = []
    
    if file_paths:
        # Clean up specific files
        files_to_cleanup.extend(file_paths)
    else:
        # Look for common temp file patterns
        search_dir = Path(".")
        glob_method = search_dir.rglob if recursive else search_dir.glob
        
        for pattern in patterns:
            matched_files = list(glob_method(pattern))
            logger.debug(f"Pattern '{pattern}' matched {len(matched_files)} files")
            files_to_cleanup.extend(matched_files)
    
    # Deduplicate files
    files_to_cleanup = list(dict.fromkeys(files_to_cleanup))
    
    cleaned: List[Path] = []
    failed: List[Tuple[Path, str]] = []
    
    for file_path in files_to_cleanup:
        try:
            if is_safe_to_delete(file_path, logger):
                if dry_run:
                    logger.info(f"Would delete: {file_path}")
                    cleaned.append(file_path)
                else:
                    file_path.unlink()
                    logger.info(f"Deleted: {file_path}")
                    cleaned.append(file_path)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to delete {file_path}: {error_msg}")
            failed.append((file_path, error_msg))
    
    return cleaned, failed


def main() -> int:
    """
    Main entry point for CLI.
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(
        description="Cleanup temporary files for paper-note skill"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"paper-note cleanup_temp v{__version__}"
    )
    
    parser.add_argument(
        "files",
        type=Path,
        nargs="*",
        help="Specific files to clean up (if not specified, uses default patterns)"
    )
    
    parser.add_argument(
        "--patterns",
        type=str,
        nargs="+",
        default=None,
        help=f"Glob patterns to match (default: {', '.join(DEFAULT_TEMP_FILE_PATTERNS)})"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Search recursively in subdirectories"
    )
    
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to JSON configuration file"
    )
    
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress non-error output"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1
    
    # Adjust logging level based on flags
    if args.verbose:
        config.logging.level = logging.DEBUG
    elif args.quiet:
        config.logging.level = logging.ERROR
    
    logger = setup_logging(config.logging)
    
    # Run cleanup
    file_paths = args.files if args.files else None
    cleaned, failed = cleanup_files(
        file_paths=file_paths,
        patterns=args.patterns,
        dry_run=args.dry_run,
        recursive=args.recursive,
        config=config,
        logger=logger,
    )
    
    # Print summary
    if cleaned:
        logger.info(f"Cleaned up {len(cleaned)} file(s)")
        if args.verbose:
            for f in cleaned:
                logger.debug(f"  - {f}")
    
    if failed:
        logger.error(f"Failed to clean up {len(failed)} file(s):")
        for f, error in failed:
            logger.error(f"  - {f}: {error}")
    
    # Return 0 even if some files failed (non-critical error)
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
