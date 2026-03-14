// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightThemeNova from 'starlight-theme-nova';

// https://astro.build/config
export default defineConfig({
	server: {
		host: true,  // 等同于 --host
		port: 4321,
	},
	vite: {
		server: {
			hmr: {
				host: 'localhost',
				port: 4321,
				protocol: 'ws',
			},
			watch: {
				usePolling: true,
				interval: 1000,
			},
		},
	},
	site: 'https://USTB-806.github.io',
	base: '/ustb-os-tutorial',
	trailingSlash: "always",
	integrations: [
		starlight({
			plugins: [starlightThemeNova()],
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
					label: '写在前面',
					autogenerate: {directory: 'preface'},
				},
				{
					label: 'Lab0. 环境配置',
					autogenerate: {directory: 'env-config'},
				},
				{
					label: 'Lab1. Rust语言基础',
					autogenerate: {directory: 'lab1'},
				},
				{
					label: 'Lab2. 批处理系统',
					autogenerate: {directory: 'lab2'},
				},
				{
					label: 'Lab3. 分时系统',
					autogenerate: {directory: 'lab3'},
				},
				{
					label: 'Lab4. 地址空间',
					autogenerate: {directory: 'lab4'},
				},
				{
					label: 'Lab5. 进程管理',
					autogenerate: {directory: 'lab5'},
				},
				{
					label: 'Lab6. 文件系统',
					autogenerate: {directory: 'lab6'},
				},
				{
					label: '杂项/附录/参考',
					autogenerate: { directory: 'reference' },
				},
			],
		}),
	],
});
