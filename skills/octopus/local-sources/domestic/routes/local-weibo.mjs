// Optional Octopus RSSHub extension using Weibo's public website hot-search response.
export const namespace = { name: "微博公开热搜", url: "weibo.com" };
const escape = (value) => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");

export function toFeed(payload) {
    if (payload?.ok !== 1 || !Array.isArray(payload?.data?.realtime)) {
        throw new Error("Weibo public hot-search response is unavailable.");
    }
    return {
        title: "微博公开热搜",
        link: "https://s.weibo.com/top/summary",
        description: "公开热搜线索；热度和抓取时间不代表事件发布时间。",
        item: payload.data.realtime.filter((row) => row.word && !row.is_ad).map((row) => ({
            title: row.word,
            link: "https://s.weibo.com/weibo?q=" + encodeURIComponent(row.word_scheme || row.word),
            description: `<p>${escape(row.word)}</p><p>热度：${escape(row.num ?? row.raw_hot ?? "未提供")}；分类：${escape(row.category ?? "未提供")}</p>`,
        })),
    };
}

export const routes = [{
    path: "/hot",
    name: "热搜榜",
    categories: ["social-media"],
    example: "/local-weibo/hot",
    features: { requirePuppeteer: false, requireConfig: false, antiCrawler: true },
    handler: async () => {
        const response = await fetch("https://weibo.com/ajax/side/hotSearch", {
            headers: { "User-Agent": "Mozilla/5.0", Referer: "https://weibo.com/" },
            signal: AbortSignal.timeout(25000),
        });
        if (!response.ok) throw new Error(`Weibo public hot-search returned HTTP ${response.status}.`);
        return toFeed(await response.json());
    },
}];
