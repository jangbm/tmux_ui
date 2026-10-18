" Local theme for new workspace editors. Does not change ~/.vimrc.
set nocompatible
set background=dark
if has('termguicolors')
  set termguicolors
endif
syntax enable
filetype plugin indent on
set number
set cursorline
set laststatus=2
set noshowmode
set ruler
set scrolloff=5
set signcolumn=yes
set fillchars=vert:\│
set statusline=\ %f\ %m%r%=%l:%c\ \ %p%%
highlight Normal guifg=#d6d6d6 guibg=#181818 ctermfg=252 ctermbg=234
highlight NonText guifg=#414141 guibg=#181818 ctermfg=238 ctermbg=234
highlight LineNr guifg=#777777 guibg=#181818 ctermfg=243 ctermbg=234
highlight CursorLineNr guifg=#b7cdb9 guibg=#222622 ctermfg=151 ctermbg=235
highlight CursorLine guibg=#222222 ctermbg=235 cterm=NONE
highlight SignColumn guibg=#181818 ctermbg=234
highlight StatusLine guifg=#d6d6d6 guibg=#303030 gui=NONE cterm=NONE
highlight StatusLineNC guifg=#a0a0a0 guibg=#202020 gui=NONE cterm=NONE
highlight VertSplit guifg=#303030 guibg=#181818 gui=NONE cterm=NONE
highlight Visual guibg=#384239 ctermbg=238
highlight Search guifg=#181818 guibg=#d9bc88
highlight Comment guifg=#8c958c ctermfg=245
highlight String guifg=#b7cdb9 ctermfg=151
highlight Constant guifg=#d9bc88 ctermfg=180
highlight Identifier guifg=#d6d6d6 ctermfg=252 cterm=NONE
highlight Function guifg=#c8c2a3 ctermfg=187
highlight Statement guifg=#b8aed1 ctermfg=146 gui=NONE
highlight PreProc guifg=#a6bfd8 ctermfg=110
highlight Type guifg=#a6bfd8 ctermfg=110 gui=NONE
highlight Special guifg=#d3ac96 ctermfg=180
highlight Pmenu guifg=#d6d6d6 guibg=#282828
highlight PmenuSel guifg=#eeeeee guibg=#384239
