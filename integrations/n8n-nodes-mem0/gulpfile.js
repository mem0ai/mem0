const path = require('path');
const { task, src, dest } = require('gulp');

task('build:icons', copyIcons);

function copyIcons() {
	// Copy icons and the codex (*.node.json) next to the compiled nodes; tsc emits
	// only .js, so these static assets need copying for n8n to pick them up.
	const nodeSource = path.resolve('nodes', '**', '*.{png,svg,json}');
	const nodeDestination = path.resolve('dist', 'nodes');
	src(nodeSource).pipe(dest(nodeDestination));

	const credSource = path.resolve('credentials', '**', '*.{png,svg}');
	const credDestination = path.resolve('dist', 'credentials');
	return src(credSource, { allowEmpty: true }).pipe(dest(credDestination));
}
