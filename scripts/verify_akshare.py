#!/usr/bin/env python3
"""验证设计文档中列出的所有 akshare API 接口是否可用。
Phase 1 的第一步：确保数据源可用后再开始开发。
"""

import sys
import time

def verify_api(name: str, func, *args, **kwargs) -> bool:
    """验证单个 API 接口。"""
    try:
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        rows = len(result) if hasattr(result, '__len__') else 'N/A'
        cols = list(result.columns)[:5] if hasattr(result, 'columns') else 'N/A'
        print(f"  ✅ {name} — {rows} rows, {elapsed:.1f}s, cols: {cols}")
        return True
    except Exception as e:
        print(f"  ❌ {name} — {type(e).__name__}: {e}")
        return False


def main():
    print("=" * 60)
    print("akshare API 可用性验证")
    print("=" * 60)

    try:
        import akshare as ak
        print(f"\nakshare version: {ak.__version__}\n")
    except ImportError:
        print("\n❌ akshare 未安装。运行: pip install akshare")
        sys.exit(1)

    results = {}
    test_stock = "600519"  # 贵州茅台

    # === 基本面分析师数据源 ===
    print("【基本面分析师】")
    results["stock_individual_info_em"] = verify_api(
        "stock_individual_info_em (个股信息)",
        ak.stock_individual_info_em, symbol=test_stock
    )
    results["stock_financial_abstract_ths"] = verify_api(
        "stock_financial_abstract_ths (财务摘要)",
        ak.stock_financial_abstract_ths, symbol=test_stock
    )

    # === 宏观分析师数据源 ===
    print("\n【宏观分析师】")
    results["macro_china_gdp"] = verify_api(
        "macro_china_gdp (中国 GDP)",
        ak.macro_china_gdp
    )
    results["stock_board_industry_name_em"] = verify_api(
        "stock_board_industry_name_em (行业板块)",
        ak.stock_board_industry_name_em
    )

    # === 情绪分析师数据源 ===
    print("\n【情绪分析师】")
    results["stock_news_em"] = verify_api(
        "stock_news_em (个股新闻)",
        ak.stock_news_em, symbol=test_stock
    )
    results["stock_hsgt_hist_em"] = verify_api(
        "stock_hsgt_hist_em (北向资金-沪股通)",
        ak.stock_hsgt_hist_em, symbol="沪股通"
    )
    results["stock_margin_account_info"] = verify_api(
        "stock_margin_account_info (融资融券)",
        ak.stock_margin_account_info
    )

    # === 补充：历史行情 ===
    print("\n【补充数据】")
    results["stock_zh_a_hist"] = verify_api(
        "stock_zh_a_hist (历史行情)",
        ak.stock_zh_a_hist, symbol=test_stock, period="daily",
        start_date="20240101", end_date="20241231", adjust="qfq"
    )

    # === 汇总 ===
    total = len(results)
    passed = sum(results.values())
    failed = total - passed

    print("\n" + "=" * 60)
    print(f"结果: {passed}/{total} 通过, {failed} 失败")

    if failed > 0:
        print("\n⚠️  部分接口不可用。失败的接口:")
        for name, ok in results.items():
            if not ok:
                print(f"  - {name}")
        print("\nakshare 是社区维护的爬虫库，接口可能因数据源网站改版而失效。")
        print("建议：检查 akshare GitHub issues 或尝试升级: pip install akshare --upgrade")
    else:
        print("\n🎉 所有接口可用！可以开始开发。")

    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
