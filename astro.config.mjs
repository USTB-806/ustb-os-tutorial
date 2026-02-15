// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightThemeRapide from 'starlight-theme-rapide';

// https://astro.build/config
export default defineConfig({
	site: 'https://USTB-806.github.io',
	base: '/ustb-os-tutorial',
	trailingSlash: "always",
	integrations: [
		starlight({
			plugins: [starlightThemeRapide()],
			title: 'USTB Operating System Tutorial',
			defaultLocale: 'root',
			locales: {
				root: {
					label: '简体中文',
					lang: 'zh-CN',
				},
			},
			social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/USTB-806/ustb-os-tutorial' }],
			customCss: [
				'./src/styles/custom.css',
			],
			sidebar: [
				{
					label: '环境配置',
					autogenerate: {directory: 'env-config'},
				},
				{
					label: 'Lab1',
					autogenerate: {directory: 'lab1'},
				},
					{
					label: 'Lab2',
					autogenerate: {directory: 'lab2'},
				},
				
				{
					label: 'Reference',
					autogenerate: { directory: 'reference' },
				},
			],
		}),
	],
});
